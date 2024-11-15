# -*- coding: utf-8 -*-
"""BottomUp Approach on Graph Classfication.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1tKyo0RvfKHOjWrnYrYxPr3eWIHqI1OkW

## ***Adaptations on the Explanations of Instance-based Methods***


> Moduled: Accpeting the four GNNs (GCN+GAP, DGCNN, DIFFPOOL, and GIN)


---

The algorithm:
Profile each edge's existance in all explanations by source and target node features.
Given a threshold, return saliency maps for each class by those of edges which satisfy the thresholding on frequency of appearance
on explanations of the target class.

"
"""

import os
import torch
os.environ['TORCH'] = torch.__version__
print(torch.__version__)
import numpy as np
from math import sqrt
import math
import torch
import statistics
import pandas
from time import perf_counter
from torch_geometric.data import Data, Batch, Dataset
import networkx as nx
from typing import List, Tuple, Dict
import tqdm
from statistics import mean


class profile_frequencies_by_edge_based_explanations:
    def __init__(self, list_of_saliencies, test_dataset, style):
        self.list_of_saliencies = list_of_saliencies
        self.edges_profile_by_node_feats = {}
        self.edges_profile_by_node_feats_2_proportions = {}
        self.test_dataset = test_dataset
        self.style = style


        self.profile_edges_for_each_explanation()
        self.get_proportions()

        # for key, value in self.edges_profile_by_node_feats_2_proportions.items():
        #     print("Key: ", key, "      ", value)

    def profile_edges_for_each_explanation(self):
        for expl, graph in zip(self.list_of_saliencies, self.test_dataset):
            graph_edges = [(source_index, target_index) for source_index, target_index in graph.edge_index.T.tolist()]
            if self.style == "Edge":
                self.get_paired_features_as_keys_by_edge_saleincy(expl, graph_edges, graph.x)
            elif self.style == "Node":
                self.get_paired_features_as_keys_by_node_saleincy(expl, graph_edges, graph.x)

    def get_paired_features_as_keys_by_edge_saleincy(self, expl, edges, node_feats):
        for edge_sal, (source_index, target_index) in zip(expl, edges):
            if edge_sal == 1:
                edge_key = tuple([tuple(node_feats[source_index].tolist()), tuple(node_feats[target_index].tolist())])
                if edge_key in self.edges_profile_by_node_feats.keys():
                    self.edges_profile_by_node_feats[edge_key] = self.edges_profile_by_node_feats[edge_key] + 1
                else:
                    self.edges_profile_by_node_feats[edge_key] = 1

    def get_paired_features_as_keys_by_node_saleincy(self, expl, edges, node_feats):
        for (source_index, target_index) in edges:
            if (expl[source_index] == 1) and (expl[target_index] == 1):
                edge_key = tuple([tuple(node_feats[source_index].tolist()), tuple(node_feats[target_index].tolist())])
                if edge_key in self.edges_profile_by_node_feats.keys():
                    self.edges_profile_by_node_feats[edge_key] = self.edges_profile_by_node_feats[edge_key] + 1
                else:
                    self.edges_profile_by_node_feats[edge_key] = 1

    def get_proportions(self):
        sum_value = sum(self.edges_profile_by_node_feats.values())
        for key, value in self.edges_profile_by_node_feats.items():
            self.edges_profile_by_node_feats_2_proportions[key] = value/sum_value

    def profile_the_upcoming_explanation(self, an_explanation, a_graph):
        profile = []
        if self.style == "Edge":
            graph_edges = [(source_index, target_index) for source_index, target_index in a_graph.edge_index.T.tolist()]
            for sal_score, (source_index, target_index) in zip(an_explanation, graph_edges):
                edge_key = tuple([tuple(a_graph.x[source_index].tolist()), tuple(a_graph.x[target_index].tolist())])
                if sal_score == 1:
                    profile.append(self.edges_profile_by_node_feats_2_proportions[edge_key])
                else:
                    profile.append(0)
            return profile

        elif self.style == "Node":
            graph_edges = [(source_index, target_index) for source_index, target_index in a_graph.edge_index.T.tolist()]
            for (source_index, target_index) in graph_edges:
                edge_key = tuple([tuple(a_graph.x[source_index].tolist()), tuple(a_graph.x[target_index].tolist())])
                if (an_explanation[source_index] == 1) and (an_explanation[target_index] == 1):
                    profile.append(self.edges_profile_by_node_feats_2_proportions[edge_key])
                else:
                    profile.append(0)
            return profile

    def __call__(self, an_explanation, a_graph, threshold):

        profile = self.profile_the_upcoming_explanation(an_explanation, a_graph)
        profile_one_hot = [1 if value > threshold else 0 for value in profile]
        return profile_one_hot



# edge_explanations = []
# node_explanations = []
# number_of_graphs = 10
# for i in range(number_of_graphs):
#     edge_explanations.extend(torch.randint(2, (1, mutag_test_dataset[i].edge_index[0].size()[0])).tolist())
#     node_explanations.extend(torch.randint(2, (1, mutag_test_dataset[i].x.size()[0])).tolist())

# print("edge_explanations: ", edge_explanations)
# print("node_explanations: ", node_explanations)

# common_edges_finder = profile_frequencies(list_of_saliencies=edge_explanations, test_dataset=mutag_test_dataset[:number_of_graphs], style="Edge")
# graph_index = 0
# profile_one_hot = common_edges_finder(edge_explanations[graph_index], mutag_test_dataset[graph_index], 0.7)
# print(" input graph number of nodes: ", len(mutag_test_dataset[graph_index].x), " input graph number of edges: ", len(mutag_test_dataset[graph_index].edge_index[0]))
# for i, value in enumerate(profile_one_hot):
#     print(i, "   ", value)