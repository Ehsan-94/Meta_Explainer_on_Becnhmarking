# -*- coding: utf-8 -*-
"""GNNInterpreter on Graph Classification Final Format.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1Ia8foQUnd9_DKyHyBggpSQ8U5JLwiN5K

## ***GNNInterpreter***


> Moduled: Accpeting the four GNNs (GCN+GAP, DGCNN, DIFFPOOL, and GIN)


---
"""

# Install required packages.
import os
import torch
import argparse
import os
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import numpy as np
from math import sqrt
from torch_geometric.datasets import TUDataset
import torch as th
import torch
import torch.nn as nn
from torch.nn.parameter import Parameter
from torch_geometric.nn import GCNConv
import torch.nn.functional as F
from torch.nn import Linear
from torch import distributions
import torch_geometric
from sklearn import metrics
from scipy.spatial.distance import hamming
import statistics
import pandas
import csv
from time import perf_counter
from torch_geometric.nn import GCNConv, global_mean_pool
from torch_geometric.loader import DataLoader
#from torch_geometric.explain import Explainer, GNNExplainer
import torch_geometric.nn as gnn
from time import perf_counter
from IPython.core.display import deepcopy
from torch_geometric.nn import MessagePassing
import copy
import random
from functools import cached_property
from typing import Optional, Literal
import networkx as nx
import pandas as pd
from tqdm.auto import tqdm
import secrets
import os
import pickle
import glob

class Graph_Generator(nn.Module):
    def __init__(self, max_nodes, num_node_classes, num_edge_classes, nodes, edges, Graph, learning_node_feat, learning_edge_feat,
                 temperature):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        if Graph:
            Graph = nx.convert_node_labels_to_integers(Graph)
            nodes = [Graph.nodes[i]['label'] for i in range(Graph.number_of_nodes())]
            edges = Graph.edges

        self.num_nodes = max_nodes or len(nodes)
        self.num_node_classes = num_node_classes or (max(nodes) if nodes is not None else 1)
        self.num_edge_classes = num_edge_classes

        self.nodes = nodes or self.generate_a_list_of_n_random_values_from_k_classes(self.num_nodes, self.num_node_classes)
        self.edges = edges or self.generate_edges_for_a_complete_graph(self.num_nodes)
        self.edge_classes = self.generate_a_list_of_n_random_values_from_k_classes(self.num_edges, self.num_edge_classes) if num_edge_classes else None
        self.tau = temperature

        #################################                       DEFINE Parameters
        self.param_list = []

        # for edge existance
        self.edge_parameters = nn.Parameter(torch.empty(self.num_edges).to(self.device))                         #omega
        self.param_list.extend(["edge_parameters", "apply_sigmoid_on_edge_parameters", "edge_parameters_pairs_of_nodes"])

        # for node existance
        if learning_node_feat:
            self.node_feature_parameters = nn.Parameter(torch.empty(self.num_nodes, self.num_node_classes).to(self.device))       #xi
            self.param_list.extend(["node_feature_parameters", "softmax_node_feature_parameters"])
        else:
            self.node_feature_parameters = None

        # for edge feature
        if learning_edge_feat:
            self.edge_feature_parameters = nn.Parameter(torch.empty(self.num_edges, self.num_edge_classes).to(self.device))       #eta
            self.param_list.extend(["edge_feature_parameters", "softmax_edge_feature_parameters"])
        else:
            self.edge_feature_parameters = None

        self.init()

    @torch.no_grad()
    def init(self, Graph=None):
        eps = 1e-4
        #                                                               For Edge Existance, theta: fuzzy values for edges: weights
        if Graph is None:
            theta = torch.rand(self.num_edges).to(self.device)
        else:
            theta_list = []
            for u, v in self.create_edge_index.T[:self.num_edges].tolist():
                if (u, v) in Graph.edges or (v, u) in Graph.edges:
                    theta_list.append(1 - eps)
                else:
                    theta_list.append(eps)
            theta = torch.stack(theta_list).to(self.device)

        self.edge_parameters.data = torch.logit(theta)

        #                                                               For Node Class
        if self.node_feature_parameters is not None:
            if Graph is None:
                p = distributions.Dirichlet(torch.ones(self.num_node_classes).to(self.device)).sample([self.num_nodes])
            else:
                for i in Graph.nodes:
                    p = torch.stack([(torch.eye(self.num_node_classes, device=self.device) * (1 - 2*eps) + eps)[Graph.nodes[i]['label']]])

            self.node_feature_parameters.data = torch.log(p)

        #                                                               For Edge Class
        if self.edge_feature_parameters is not None:
            if Graph is None:
                q = distributions.Dirichlet(torch.ones(self.num_edge_classes).to(self.device)).sample([self.num_edges])
            else:
                q_list = []
                for u, v in self.create_edge_index.T[:self.num_edges].tolist():
                    if (u, v) in Graph.edges:
                        q_list.append((torch.eye(self.num_edge_classes, device=self.device) * (1 - 2*eps) + eps)[Graph.edges[(u, v)]['label']])
                    else:
                        if (v, u) in Graph.edges:
                            q_list.append((torch.eye(self.num_edge_classes, device=self.device) * (1 - 2*eps) + eps)[Graph.edges[(v, u)]['label']])
                        else:
                            q_list.append(torch.zeros(self.num_edge_classes, device=self.device) + eps)
                q = torch.stack(q_list)

            self.edge_feature_parameters.data = torch.log(q)

    @staticmethod
    def generate_a_list_of_n_random_values_from_k_classes(number_of_rows, number_of_columns):
        return random.choices(range(number_of_columns), k=number_of_rows)

    @staticmethod
    def generate_edges_for_a_complete_graph(n):
        return [(i, j) for i in range(n) for j in range(n) if i < j]

    @cached_property
    def num_edges(self):
        return len(self.edges)

    @cached_property
    def create_edge_index(self) -> torch.Tensor:
        edges = ([(i, j) for i, j in self.edges] +
                 [(j, i) for i, j in self.edges])
        assert len(edges) == self.num_edges * 2
        return torch.tensor(edges).T

    def sample_epsilon(self, target, seed=None, if_not_seed_equal_chance=False):
        if if_not_seed_equal_chance:
            return torch.ones_like(target) / 2
        else:
            if seed is not None:
                torch.manual_seed(seed)
            else:
                torch.seed()
            return torch.rand_like(target)

    def sample_Adjacency(self, seed=None, if_not_seed_equal_chance=False):
        #   Equation 5th
        eps = self.sample_epsilon(self.edge_parameters, seed=seed,
                                  if_not_seed_equal_chance=if_not_seed_equal_chance)
        logistic = torch.logit(eps)
        A = torch.sigmoid((self.edge_parameters + logistic) / self.tau)
        return torch.cat([A, A], dim=0)

    def sample_Node_Features(self, seed=None, if_not_seed_equal_chance=False):
        #   Equation 5th
        if self.node_feature_parameters is not None:
            eps = self.sample_epsilon(self.node_feature_parameters, seed=seed,
                                      if_not_seed_equal_chance=if_not_seed_equal_chance)
            gumbel = -torch.log(-torch.log(eps))
            X = torch.softmax((self.node_feature_parameters + gumbel) / self.tau, dim=1)
            return X
        else:
            return torch.eye(self.num_node_classes, device=self.device)[self.nodes]

    def sample_Edge_Features(self, seed=None, if_not_seed_equal_chance=False):
        #   Equation 5th
        if self.edge_feature_parameters is not None:
            eps = self.sample_epsilon(self.edge_feature_parameters, seed=seed,
                                      if_not_seed_equal_chance=if_not_seed_equal_chance)
            gumbel = -torch.log(-torch.log(eps))
            E = torch.softmax((self.edge_feature_parameters + gumbel) / self.tau, dim=1)
        elif self.num_edge_classes:
            E = torch.eye(self.num_edge_classes, device=self.device)[self.edge_classes]
        else:
            return None
        return torch.cat([E, E], dim=0)

    @property
    def edge_parameters_pairs_of_nodes(self):
        return self.apply_sigmoid_on_edge_parameters[self.edge_parameters.long()]

    def attributes_into_dict(self):
        my_dict = {}
        for item in self.param_list:
            my_dict[item] = getattr(self, item)
        return my_dict

    @property
    def softmax_node_feature_parameters(self):
        return torch.softmax(self.node_feature_parameters, dim=1)

    @property
    def softmax_edge_feature_parameters(self):
        return torch.softmax(self.edge_feature_parameters, dim=1)

    @property
    def apply_sigmoid_on_edge_parameters(self):
        return torch.sigmoid(self.edge_parameters)

    @cached_property
    def pair_index_for_each_edge(self):
        edges = self.edge_index.T[:self.num_edges]
        pairs = [(i, j)
                 for i in range(self.num_edges-1)
                 for j in range(i+1, self.num_edges)
                 if edges[i][0] == edges[j][0]]
        return torch.tensor(pairs).T

    @property
    def expected_number_of_edges_in_the_generated_graph(self):
        return self.apply_sigmoid_on_edge_parameters.sum().item()

    def forward(self, batch_size_for_same_sized_graphs, mode, seed, if_not_seed_equal_chance):

        X = self.sample_Node_Features(seed=seed, if_not_seed_equal_chance=if_not_seed_equal_chance)
        A = self.sample_Adjacency(seed=seed, if_not_seed_equal_chance=if_not_seed_equal_chance)     # With Respect to Edge Weight.
        E = self.sample_Edge_Features(seed=seed, if_not_seed_equal_chance=if_not_seed_equal_chance)
        continuous_data, discrete_data = None, None

        if mode in ['continuous', 'both']:
            data_list = []
            for _ in range(batch_size_for_same_sized_graphs):
                data_list.append(torch_geometric.data.Data(x=X, edge_index=self.create_edge_index, edge_weight=A,
                                                           edge_attr=E))
            continuous_data = torch_geometric.data.Batch.from_data_list(data_list)

        if mode in ['discrete', 'both']:
            edge_attr_list = []
            for _ in range(batch_size_for_same_sized_graphs):
                if self.edge_feature_parameters is not None:
                    edge_attr_list.append(torch_geometric.data.Data(
                        x=torch.eye(self.num_node_classes, device=self.device)[X.argmax(dim=-1)].float(),
                        edge_index=self.create_edge_index, edge_weight=(A > 0.5).float(),
                        edge_attr=torch.eye(self.num_edge_classes)[E.argmax(dim=-1)].float()))
                else:
                    edge_attr_list.append(torch_geometric.data.Data(
                        x=torch.eye(self.num_node_classes, device=self.device)[X.argmax(dim=-1)].float(),
                        edge_index=self.create_edge_index, edge_weight=(A > 0.5).float(),
                        edge_attr=E))

            discrete_data = torch_geometric.data.Batch.from_data_list(edge_attr_list)

        if mode == 'both':
            return continuous_data, discrete_data

        elif mode == 'continuous':
            return continuous_data

        elif mode == 'discrete':
            return discrete_data


class Generation_Manager_wrt_Classes:
    def __init__(self, generator, discriminator, aggregate_losses, optimizer, dataset,
                 budget_penalty, targeted_probabilities, batch_size_for_same_sized_graphs):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.batch_size_for_same_sized_graphs = batch_size_for_same_sized_graphs
        self.targeted_probabilities = targeted_probabilities
        self.generator = generator.to(self.device)
        self.discriminator = discriminator.to(self.device)
        self.aggregate_losses = aggregate_losses
        self.budget_penalty = budget_penalty or None
        self.optimizer = optimizer if isinstance(optimizer, list) else [optimizer]
        self.dataset = dataset
        self.iteration = 0

    def train(self, explanation_epochs):
        self.bkup_state = copy.deepcopy(self.generator.state_dict())
        self.bkup_aggregate_losses = copy.deepcopy(self.aggregate_losses)
        self.bkup_iteration = self.iteration

        self.discriminator.eval()
        self.generator.train()
        budget_penalty_weight = 1
        for _ in (tqdm(range(explanation_epochs))):
            for opt in self.optimizer:
                opt.zero_grad()

            continuous_generated_graph = self.generator(
                batch_size_for_same_sized_graphs=self.batch_size_for_same_sized_graphs, mode='continuous', seed=None,
                if_not_seed_equal_chance=False)
            discrete_generated_graph = self.generator(
                batch_size_for_same_sized_graphs=1, mode='discrete', seed=None, if_not_seed_equal_chance=False)
            # TODO: potential bug
            continuous_generated_graph = continuous_generated_graph.to(self.device)
            discrete_generated_graph = discrete_generated_graph.to(self.device)

            if self.discriminator.__class__.__name__ == "GCN_plus_GAP_Model":
                Output_of_Hidden_Layers_continuous, pooling_layer_output_continuous, ffn_output_continuous, pred_for_continuous_generated_graph = self.discriminator(continuous_generated_graph, None)
                Output_of_Hidden_Layers_discrete, pooling_layer_output_discrete, ffn_output_discrete, pred_for_discrete_generated_graph = self.discriminator(discrete_generated_graph, None)
            elif self.discriminator.__class__.__name__ == "DGCNN_Model":
                final_GNN_layer_output, sortpooled_embedings, output_conv1d_1, maxpooled_output_conv1d_1, output_conv1d_2, to_dense, output_h1, dropout_output_h1, ffn_output_continuous, pred_for_continuous_generated_graph = self.discriminator(continuous_generated_graph, None)
                final_GNN_layer_output, sortpooled_embedings, output_conv1d_1, maxpooled_output_conv1d_1, output_conv1d_2, to_dense, output_h1, dropout_output_h1, ffn_output_discrete, pred_for_discrete_generated_graph = self.discriminator(discrete_generated_graph, None)
            elif self.discriminator.__class__.__name__ == "DIFFPOOL_Model":
                concatination_list_of_poolings, ffn_output_continuous, pred_for_continuous_generated_graph = self.discriminator(continuous_generated_graph, None)
                concatination_list_of_poolings, ffn_output_discrete, pred_for_discrete_generated_graph = self.discriminator(discrete_generated_graph, None)
            elif self.discriminator.__class__.__name__ == "GIN_Model":
                mlps_output_embeds, mlp_outputs_globalSUMpooled, lin1_output, lin1_output_dropouted, ffn_output_continuous, pred_for_continuous_generated_graph = self.discriminator(continuous_generated_graph, None)
                mlps_output_embeds, mlp_outputs_globalSUMpooled, lin1_output, lin1_output_dropouted, ffn_output_discrete, pred_for_discrete_generated_graph = self.discriminator(discrete_generated_graph, None)


            if self.targeted_probabilities and all([
                min_probability <= pred_for_discrete_generated_graph[0, class_of_explanation] <= max_probability
                for class_of_explanation, (min_probability, max_probability) in self.targeted_probabilities.items()
            ]):

                if self.budget_penalty and (self.generator.expected_number_of_edges_in_the_generated_graph <= self.budget_penalty.budget):
                    break
                budget_penalty_weight *= 1.1
            else:
                budget_penalty_weight *= 0.95



            evaluation_dict = self.generator.attributes_into_dict()
            evaluation_dict['continuous_generated_embeddings'] = continuous_generated_graph.x
            evaluation_dict['logits_continuous'] = ffn_output_continuous
            evaluation_dict['discrete_generated_embeddings'] = discrete_generated_graph.x
            evaluation_dict['logits_discrete'] = ffn_output_discrete


            loss = self.aggregate_losses(evaluation_dict)
            if self.budget_penalty:
                loss += self.budget_penalty(self.generator.apply_sigmoid_on_edge_parameters) * budget_penalty_weight
            loss.backward()


            self.iteration += 1
        return continuous_generated_graph, discrete_generated_graph




class Embedding_Loss_by_Cosine_Similarity(nn.Module):
    def __init__(self, target_embedding):
        super().__init__()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.target = target_embedding.to(self.device)

    def forward(self, embeds):
        embeds = embeds.to(self.device)
        assert len(embeds.shape) == 2
        return (1 - F.cosine_similarity(self.target[None, :], embeds)).mean()

class Explanation_Class_Score(nn.Module):
    def __init__(self, class_idx, mode='maximize', logsoftmax=False):
        super().__init__()
        self.class_idx = class_idx
        self.mode = mode
        self.logsoftmax = logsoftmax

    def forward(self, logits):
        assert len(logits.shape) == 2
        if self.logsoftmax:
            logits = F.log_softmax(logits)
        score = logits[:, self.class_idx].mean()
        if self.mode == 'maximize':
            return -score
        elif self.mode == 'minimize':
            return score
        else:
            raise NotImplemented

class MeanPenalty(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        return x.mean()

class NormPenalty(nn.Module):
    def __init__(self, order=2):
        super().__init__()
        self.order = order

    def forward(self, x):
        return x.norm(p=self.order)

class BudgetPenalty_for_second_regularization(nn.Module):
    def __init__(self, budget=0, order=1, beta=1):
        super().__init__()
        self.budget = budget
        self.beta = beta
        self.order = order

    def forward(self, theta):
        return F.softplus(theta.sum() - self.budget, beta=self.beta) ** self.order

class KLDivergencePenalty(nn.Module):
    def __init__(self, binary=True, eps=1e-4):
        super().__init__()
        self.binary = binary
        self.eps = eps

    def forward(self, pq):
        p = pq[0] * (1 - 2*self.eps) + self.eps
        q = pq[1] * (1 - 2*self.eps) + self.eps
        if self.binary:
            p = torch.stack([p, 1-p], dim=-1)
            q = torch.stack([q, 1-q], dim=-1)
        return torch.sum(p * (p / q).log())

class losses_aggregation(nn.Module):
    def __init__(self, criteria):
        super().__init__()
        self.criteria = criteria

    def forward(self, my_input):
        loss = 0
        for criterion in self.criteria:
            loss += criterion["criterion"](my_input[criterion["key"]]) * criterion["weight"]
        return loss

#class_of_explanation = 0

#Generation_Manager_wrt_Classes_dict = {}
#sampler = {}

#mean_embeds_class_entire = torch.mean(torch.cat([graph.x for graph in mutag_test_dataset], dim=0), axis=0)
#mean_embeds_class_one = torch.mean(torch.cat([graph.x for graph in mutag_test_dataset if graph.y == 1], dim=0), axis=0)
#mean_embeds_class_zero = torch.mean(torch.cat([graph.x for graph in mutag_test_dataset if graph.y == 0], dim=0), axis=0)
#losses_aggregated = losses_aggregation(
#    [
#        dict(key="continuous_generated_embeddings", criterion=Embedding_Loss_by_Cosine_Similarity(target_embedding=mean_embeds_class_one), weight=10),
#        dict(key="discrete_generated_embeddings", criterion=Embedding_Loss_by_Cosine_Similarity(target_embedding=mean_embeds_class_one), weight=10),
#        dict(key="logits_continuous", criterion=Explanation_Class_Score(class_idx=class_of_explanation, mode='maximize'), weight=1),
#        dict(key="logits_continuous", criterion=MeanPenalty(), weight=0),
#        dict(key="logits_discrete", criterion=Explanation_Class_Score(class_idx=class_of_explanation, mode='maximize'), weight=1),
#        dict(key="logits_discrete", criterion=MeanPenalty(), weight=0),
#        dict(key="edge_parameters", criterion=NormPenalty(order=1), weight=1),
#        dict(key="edge_parameters", criterion=NormPenalty(order=2), weight=1),
#        dict(key="node_feature_parameters", criterion=NormPenalty(order=1), weight=0),
#        dict(key="node_feature_parameters", criterion=NormPenalty(order=2), weight=0),
#        # dict(key="edge_feature_parameters", criterion=NormPenalty(order=1), weight=0),
#        # dict(key="edge_feature_parameters", criterion=NormPenalty(order=2), weight=0),
#        dict(key="edge_parameters_pairs_of_nodes", criterion=KLDivergencePenalty(binary=True), weight=0)
#        ]
#    )

#generator = Graph_Generator(max_nodes=10, num_node_classes=7, num_edge_classes=4, nodes=None, edges=None, Graph=None,
#                            learning_node_feat=True, learning_edge_feat=False, temperature=0.15)
#Generation_Manager_wrt_Classes_dict[class_of_explanation] = Generation_Manager_wrt_Classes(generator=generator, discriminator=GNN_Model,
#                                                                                           aggregate_losses=losses_aggregated,
#                                                                                           optimizer=(o := torch.optim.SGD(generator.parameters(), lr=1)),
#                                                                                           dataset=mutag_test_dataset,
#                                                                                           budget_penalty=BudgetPenalty_for_second_regularization(budget=10, order=2, beta=1),
#                                                                                           targeted_probabilities={class_of_explanation: (0.9, 1)},
#                                                                                           batch_size_for_same_sized_graphs=1)

#explanation_epochs = 2000
#continuous_generated_graph, discrete_generated_graph = Generation_Manager_wrt_Classes_dict[class_of_explanation].train(explanation_epochs)

#print(discrete_generated_graph)

#print(discrete_generated_graph.x)