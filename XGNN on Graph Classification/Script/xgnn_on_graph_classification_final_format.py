# -*- coding: utf-8 -*-
"""XGNN on Graph Classification Final Format.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Ub61R02-fF88svWadDMHLW8pjHueCYON

## ***XGNN***


> Moduled: Accpeting the four GNNs (GCN+GAP, DGCNN, DIFFPOOL, and GIN)


---
"""

import os
import torch
import argparse
import os
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np
from math import sqrt
import math
from torch_geometric.datasets import TUDataset
import torch as th
import torch
import torch.nn as nn
from torch import Tensor
from torch.nn.parameter import Parameter
from torch_geometric.nn import GCNConv
import torch.nn.functional as F
from torch.nn import Linear, LayerNorm
from sklearn import metrics
from scipy.spatial.distance import hamming
import statistics
import pandas
from time import perf_counter
from IPython.core.display import deepcopy
from torch_geometric.nn import MessagePassing
import copy
from torch.nn import ReLU, Sequential
from torch import sigmoid
from itertools import chain
from time import perf_counter
from torch_geometric.data import Data, Batch, Dataset
from functools import partial
from torch_geometric.utils import to_networkx
from torch_geometric.utils import remove_self_loops
from typing import Callable, Union, Optional
import networkx as nx
from typing import List, Tuple, Dict
from collections import Counter
import statistics
from tqdm.auto import tqdm
import csv
from statistics import mean
from torch_geometric.utils import from_scipy_sparse_matrix
from torch_geometric.nn import GCNConv, global_mean_pool
from torch_geometric.loader import DataLoader
import torch_geometric.nn as gnn
from torch.nn.modules.module import Module
from torch.nn import Linear
from torch.nn import ReLU6
from torch.nn import Sequential
import random
from torch_geometric.data import Data
from torch_geometric.utils import to_undirected
import copy




class XGNN_Graph_Generator(nn.Module):
    def __init__(self, GNN_Model, num_node_features, candidate_set_length, max_number_of_nodes, random_start, class_of_explanation,
                 hyp_for_rollout, hyp_for_rules, dropout_rate, rollout_count, dataset_name):
        super(XGNN_Graph_Generator, self).__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.dataset_name = dataset_name
        self.num_node_features = num_node_features
        self.candidate_set_length = candidate_set_length # Node Feature Dimensionality
        self.max_number_of_nodes = max_number_of_nodes
        self.random_start = random_start
        self.hyp_for_rollout = hyp_for_rollout
        self.hyp_for_rules = hyp_for_rules
        self.dropout_rate = dropout_rate
        self.rollout_count = rollout_count
        self.class_of_explanation = class_of_explanation
        self.GNN_Model = GNN_Model.to(self.device)
        self.candidate_set = ['C.4', 'N.5', 'O.2', 'F.1', 'I.7', 'Cl.7', 'Br.5']
        self.node_valency = {"MUTAG": {0: 4, 1: 5, 2: 2, 3: 1, 4: 7, 5: 7, 6: 5},
                             "IsCyclic": {0: 10, 1: 10, 2: 10, 3: 10, 4: 10, 5: 10, 6: 10, 7: 10, 8: 10, 9: 10}}
        self.candidate_set_dict = self.node_valency[self.dataset_name]#{0: 4, 1: 5, 2: 2, 3: 1, 4: 7, 5: 7, 6: 5}
        #for param in self.GNN_Model.parameters():
        #    param.requires_grad = False
        self.GNN_Model.eval()

        # The first Dense layer
        self.the_first_dense = torch.nn.Linear(self.num_node_features, 8).to(self.device)

        # GCN Layers
        self.explainer_gcn_layers = nn.ModuleList([
            #Sparse_GCN(8, 16),
            #Sparse_GCN(16, 24),
            #Sparse_GCN(24, 32)
            GCNConv(8, 16).to(self.device),
            GCNConv(16, 24).to(self.device),
            GCNConv(24, 32).to(self.device)
        ])

        # MLP1 for source node
        # 2 FC layers with hidden dimension 16
        self.mlp_source_node = torch.nn.Sequential(
            torch.nn.Linear(32, 16).to(self.device),
            torch.nn.ReLU6().to(self.device),
            torch.nn.Linear(16, 1).to(self.device),
            torch.nn.Softmax(dim=0).to(self.device)
        )

        # MLP2 for target node
        # 2 FC layers with hidden dimension 24
        self.mlp_target_node = torch.nn.Sequential(
            torch.nn.Linear(64, 24).to(self.device),
            torch.nn.ReLU6().to(self.device),
            torch.nn.Linear(24, 1).to(self.device),
            torch.nn.Softmax(dim=0).to(self.device)
        )
        self.intialize_random_graph()
        self.to(self.device)

    def intialize_random_graph(self):

        if self.random_start == True:
            self.starting_random_node_type = random.choice(np.arange(0, self.candidate_set_length))

        adj = torch.zeros((self.max_number_of_nodes + self.candidate_set_length,
                           self.max_number_of_nodes + self.candidate_set_length),
                          dtype=torch.float32, device=self.device)
        feat = torch.zeros((self.max_number_of_nodes + self.candidate_set_length, self.candidate_set_length),
                           dtype=torch.float32, device=self.device)

        feat[0, self.starting_random_node_type] = 1
        feat[np.arange(-self.candidate_set_length, 0), np.arange(0, self.candidate_set_length)] = 1

        degrees = torch.zeros(self.max_number_of_nodes, device=self.device)

        mask_candidate_set = torch.BoolTensor([False if i == 0 else True for i in range(self.candidate_set_length + self.max_number_of_nodes)]).to(self.device)

        self.Graph = {'adj': adj, 'feat': feat, 'degrees': degrees, 'num_nodes': 1,
                      'mask_candidate_set': mask_candidate_set}
        # print("A random graph is initialized.")

    def compute_reward_for_graph_rules(self, Graph):
        """
        For mutag, node degrees cannot exceed valency
        """
        try:
            for i, deg in enumerate(Graph['degrees']):
                if deg != 0:
                    node_id = torch.argmax(Graph['feat'][i]).tolist()  # Eg. [0, 1, 0, 0] -> 1
                    #node = self.candidate_set[node_id]  # Eg ['C.4', 'F.2', 'Br.7'][1] = 'F.2'
                    #max_valency = int(node.split('.')[1])  # Eg. C.4 -> ['C', '4'] -> 4
                    max_valency = int(self.candidate_set_dict[node_id])

                    # If any node degree exceeds its valency, return -1
                    if max_valency < deg:
                        return -1
            return 0
        except:
            return 0


    def compute_reward_for_model_feedback(self, Graph):
        """
        p(f(Graph) = c) - 1/l
        where l denotes number of possible classes for f
        """

        row, col = Graph['adj'].nonzero().t()
        edge_index = to_undirected([row, col])
        data = Data(x=Graph['feat'][:Graph['num_nodes']], edge_index=edge_index)
        data = data.to(self.device)

        if self.GNN_Model.__class__.__name__ == "GCN_plus_GAP_Model":
            Output_of_Hidden_Layers, pooling_layer_output, ffn_output, gnn_model_output = self.GNN_Model(data, None)
        elif self.GNN_Model.__class__.__name__ == "DGCNN_Model":
            final_GNN_layer_output, sortpooled_embedings, output_conv1d_1, maxpooled_output_conv1d_1, output_conv1d_2, to_dense, output_h1, dropout_output_h1, output_h2, gnn_model_output = self.GNN_Model(data, None)
        elif self.GNN_Model.__class__.__name__ == "DIFFPOOL_Model":
            concatination_list_of_poolings, prediction_output_not_softed, gnn_model_output = self.GNN_Model(data, None)
        elif self.GNN_Model.__class__.__name__ == "GIN_Model":
            mlps_output_embeds, mlp_outputs_globalSUMpooled, lin1_output, lin1_output_dropouted, lin2_output, gnn_model_output = self.GNN_Model(data, None)

        return (torch.squeeze(gnn_model_output).tolist()[self.class_of_explanation] - 1) / len(torch.squeeze(gnn_model_output).tolist())


    def calculate_total_reward(self, Graph):

        reward_t_for_rules = self.compute_reward_for_graph_rules(Graph)
        #print("reward_t_for_rules passed: ", reward_t_for_rules)

        reward_t_for_model_feedback = self.compute_reward_for_model_feedback(Graph)
        #print("reward_t_for_model_feedback passed: ", reward_t_for_model_feedback)

        reward_t_for_model_feedback_sum = 0
        for m in range(self.rollout_count):
            source_node_probs, best_source_node_idx, target_node_probs, best_target_node_idx, Graph = self.forward(Graph)
            reward_t_for_model_feedback_sum += self.compute_reward_for_model_feedback(Graph)
        reward_t_for_model_feedback = reward_t_for_model_feedback + (reward_t_for_model_feedback_sum * self.hyp_for_rollout) / self.rollout_count

        return reward_t_for_model_feedback + self.hyp_for_rules * reward_t_for_rules

    def calculate_loss(self, total_reward_t, source_node_probs, best_source_node_idx, target_node_probs, best_target_node_idx, Graph):

        Lce_start = F.cross_entropy(torch.reshape(source_node_probs, (1, self.max_number_of_nodes+self.candidate_set_length)),
                                    best_source_node_idx.unsqueeze(0))
        Lce_end = F.cross_entropy(torch.reshape(target_node_probs, (1, self.max_number_of_nodes+self.candidate_set_length)),
                                  best_target_node_idx.unsqueeze(0))

        return -total_reward_t * (Lce_start + Lce_end)

    def forward(self, Graph):
        Graph_copy = copy.deepcopy(Graph)
        x = Graph_copy['feat'].to(self.device)
        adj = Graph_copy['adj'].to(self.device)
        edge_index = adj.nonzero().t().contiguous().to(self.device)

        x = F.dropout(F.relu6(self.the_first_dense(x)), p=self.dropout_rate, training=True)
        for gcn_layer in self.explainer_gcn_layers:
            x = F.dropout(F.relu6(gcn_layer(x, edge_index)), p=self.dropout_rate, training=True)

        first_mlp_output = self.mlp_source_node(x)
        source_node_probs = first_mlp_output.masked_fill(Graph_copy['mask_candidate_set'].unsqueeze(1).to(self.device), 0)
        best_source_node_idx = torch.argmax(source_node_probs.masked_fill(Graph_copy['mask_candidate_set'].unsqueeze(1).to(self.device), -1))

        x1, x2 = torch.broadcast_tensors(x, x[best_source_node_idx])
        x = torch.cat((x1, x2), 1)

        mask_for_target_node = torch.BoolTensor([True for i in range(self.candidate_set_length + self.max_number_of_nodes)]).to(self.device)
        mask_for_target_node[self.max_number_of_nodes:] = False
        mask_for_target_node[:Graph_copy['num_nodes']] = False
        mask_for_target_node[best_source_node_idx] = True

        target_mlp_output = self.mlp_target_node(x)
        target_node_probs = target_mlp_output.masked_fill(mask_for_target_node.unsqueeze(1), 0)

        best_target_node_idx = torch.argmax(target_node_probs.masked_fill(mask_for_target_node.unsqueeze(1), -1))


        # Action = Add new Edge
        if Graph_copy['mask_candidate_set'][best_target_node_idx] == False:
            adj_cloned = Graph_copy['adj'].detach().clone().to(self.device)
            adj_cloned[best_source_node_idx][best_target_node_idx] = 1
            adj_cloned[best_target_node_idx][best_source_node_idx] = 1
            Graph_copy['adj'] = adj_cloned

            # Update degree vector
            Graph_copy['degrees'][best_source_node_idx] = Graph_copy['degrees'][best_source_node_idx] + 1
            Graph_copy['degrees'][best_target_node_idx] = Graph_copy['degrees'][best_target_node_idx] + 1


        # Action = Add new Node and new Edge
        elif Graph_copy['mask_candidate_set'][best_target_node_idx] == True:
            # Add a node
            feat_cloned = Graph_copy['feat'].detach().clone().to(self.device)
            feat_cloned[Graph_copy['num_nodes']] = feat_cloned[best_target_node_idx]
            Graph_copy['feat'] = feat_cloned

            # Add an edge
            adj_cloned = Graph_copy['adj'].detach().clone().to(self.device)
            adj_cloned[best_source_node_idx][Graph_copy['num_nodes']] = 1
            adj_cloned[Graph_copy['num_nodes']][best_source_node_idx] = 1
            Graph_copy['adj'] = adj_cloned

            # Update degree vector
            Graph_copy['degrees'][best_source_node_idx] = Graph_copy['degrees'][best_source_node_idx] + 1
            Graph_copy['degrees'][Graph_copy['num_nodes']] = Graph_copy['degrees'][Graph_copy['num_nodes']] + 1

            mask_candidate_set_copy = Graph_copy['mask_candidate_set'].detach().clone().to(self.device)
            mask_candidate_set_copy[Graph_copy['num_nodes']] = False
            Graph_copy['mask_candidate_set'] = mask_candidate_set_copy
            Graph_copy['num_nodes'] += 1


        return source_node_probs, best_source_node_idx, target_node_probs, best_target_node_idx, Graph_copy

class XGNN_training:
    def __init__(self, GNN_Model, max_geneneration_iterations, num_node_features, candidate_set_length,
                 max_number_of_nodes, random_start, rollout_count, class_of_explanation, hyp_for_rollout, hyp_for_rules,
                 dropout_rate, explainer_lr, b1, b2, weight_decay, dataset_name):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.GNN_Model = GNN_Model.to(self.device)
        self.num_node_features = num_node_features
        self.candidate_set_length = candidate_set_length
        self.max_number_of_nodes = max_number_of_nodes
        self.random_start = random_start
        self.rollout_count = rollout_count
        self.class_of_explanation = class_of_explanation
        self.hyp_for_rollout = hyp_for_rollout
        self.hyp_for_rules = hyp_for_rules
        self.dropout_rate = dropout_rate
        self.explainer_lr = explainer_lr
        self.b1 = b1
        self.b2 = b2
        self.weight_decay = weight_decay
        self.max_geneneration_iterations = max_geneneration_iterations
        self.dataset_name = dataset_name

        self.xgnn_explainer = XGNN_Graph_Generator(GNN_Model=self.GNN_Model, num_node_features=self.num_node_features,
                                                   candidate_set_length=self.candidate_set_length,
                                                   max_number_of_nodes=self.max_number_of_nodes,
                                                   dropout_rate=self.dropout_rate,
                                                   random_start=self.random_start, rollout_count=self.rollout_count,
                                                   class_of_explanation=self.class_of_explanation,
                                                   hyp_for_rollout=self.hyp_for_rollout,
                                                   hyp_for_rules=self.hyp_for_rules,
                                                   dataset_name=self.dataset_name).to(self.device)

        self.explainer_optimizer = torch.optim.Adam(self.xgnn_explainer.parameters(), weight_decay=self.weight_decay,
                                                    lr=self.explainer_lr, betas=(self.b1, self.b2))

    def train_generator(self):
        self.xgnn_explainer.intialize_random_graph()
        Graph = copy.deepcopy(self.xgnn_explainer.Graph)
        self.xgnn_explainer.train()
        self.explainer_optimizer.zero_grad()
        for i in range(self.max_geneneration_iterations):
            self.explainer_optimizer.zero_grad()

            source_node_probs, best_source_node_idx, target_node_probs, best_target_node_idx, Graph = self.xgnn_explainer(Graph)

            total_reward_t = self.xgnn_explainer.calculate_total_reward(Graph)

            loss = self.xgnn_explainer.calculate_loss(total_reward_t, source_node_probs, best_source_node_idx, target_node_probs, best_target_node_idx, Graph)

            loss.backward(retain_graph=True)
            self.explainer_optimizer.step()

            if Graph['num_nodes'] >= self.max_number_of_nodes:
                self.xgnn_explainer.intialize_random_graph()
                print("Number of nodes passed the threshold.")
            elif total_reward_t > 0:
                self.xgnn_explainer.Graph = Graph
                #print("total_reward_t: ", total_reward_t)
            #print("Generation iTeration: ", i)
        return Graph

    def __call__(self, explainer_epochs):
        for i in tqdm(range(explainer_epochs)):
            trained_graph = self.train_generator()
            #print("Number of nodes: ", trained_graph['num_nodes'])
        #print(trained_graph['adj'].nonzero().t().contiguous())
        trained_graph['adj'] = trained_graph['adj'].nonzero().t().contiguous().to(self.device)
        return trained_graph

#xgnn_training = XGNN_training(GNN_Model=GNN_Model, max_geneneration_iterations=10, num_node_features=7, candidate_set_length=7,
#                              max_number_of_nodes=38, random_start=True, rollout_count=10, class_of_explanation=1, hyp_for_rollout=1,
#                              hyp_for_rules=2, dropout_rate=0.5, explainer_lr=0.01, b1=0.9, b2=0.999, weight_decay=5e-4)
#xgnn_training(explainer_epochs=10)
