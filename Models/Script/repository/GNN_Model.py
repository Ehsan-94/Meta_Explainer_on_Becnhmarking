# -*- coding: utf-8 -*-
"""Implementation of GNNExplainer.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1EWa6LEBkMaQ1jVpQznkhGern7x-5EX3r
"""



import argparse
import os
import torch as th
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from torch_geometric.nn import GCNConv
import torch.nn.functional as F
from torch.nn import Linear
from sklearn.model_selection import train_test_split
import numpy as np
from torch_geometric.datasets import TUDataset
from torch_geometric.nn import GCNConv, global_mean_pool
from torch_geometric.loader import DataLoader
from torch_geometric.explain import Explainer, GNNExplainer
import torch_geometric.nn as gnn


class GlobalMeanPool(nn.Module):

    def __init__(self):
        super().__init__()

    def forward(self, x, batch):
        return gnn.global_mean_pool(x, batch)
################################################################################
class IdenticalPool(nn.Module):

    def __init__(self):
        super().__init__()

    def forward(self, x, batch):
        return x

################################################################################
class Graph_Net(torch.nn.Module):
    def __init__(self, model_name, model_level, input_dim, hidden_dim, output_dim, num_hid_layers, 
                 pred_hidden_dims=[], concat=True, bn=True, dropout=0.0, 
                 add_self=False, args=None):
        if model_name == 'GCN+GAP':
            super(Graph_Net, self).__init__()
            self.input_dim = input_dim
            print ('Graph_Net Input_Dimension:', self.input_dim)

            self.hidden_dim = hidden_dim
            print ('Graph_Net Hidden_Dimension:', self.hidden_dim)

            self.output_dim = output_dim
            print ('Graph_Net Output_Dimension:', self.output_dim)

            self.num_hid_layers = num_hid_layers
            print ('Graph_Net Number_of_Hidden_Layers:', self.num_hid_layers)


            self.args = args
            self.dropout = dropout
            self.act = F.relu

            self.GConvs = torch.nn.ModuleList()

            self.GConvs.append(GCNConv(self.input_dim, self.hidden_dim))

            for layer in range(self.num_hid_layers):
                self.GConvs.append(GCNConv(self.hidden_dim, self.hidden_dim))

            #self.GConvs.append(GCNConv(self.hidden_dim, self.output_dim))
            print('len(self.GConvs):', len(self.GConvs))

            if model_level == 'node':
                self.readout = IdenticalPool()
            else:
                self.readout = GlobalMeanPool()

            #self.ffn = nn.Linear(self.output_dim, self.output_dim, bias=False)
            self.ffn = nn.Linear(self.hidden_dim, self.output_dim, bias=False)

        else:
            print('Model is not defined well.')


    def forward(self, data):
        x, edge_index, batch = data.x, data.edge_index, data.batch
        Output_of_Hidden_Layers = []
        for i in range(self.num_hid_layers + 1):
            x = self.GConvs[i](x, edge_index)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            Output_of_Hidden_Layers.append(x)

        pooling_layer_output = self.readout(x, batch)
        ffn_output = self.ffn(pooling_layer_output)
        ffn_output = F.relu(ffn_output)

        log_soft = F.log_softmax(ffn_output, dim=1)
        soft = F.softmax(log_soft, dim=1)

        return Output_of_Hidden_Layers, pooling_layer_output, ffn_output, log_soft, soft

#GNN_Model = Graph_Net(model_name='GCN+GAP', model_level='graph', input_dim=7, hidden_dim=7, output_dim=2, num_hid_layers=1)