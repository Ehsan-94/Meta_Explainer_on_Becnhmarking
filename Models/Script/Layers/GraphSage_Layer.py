from torch_geometric.typing import Adj, OptPairTensor, Size, SparseTensor
import torch
import torch.nn as nn
import matrix_util as Mat_Util
import torch.nn.functional as F
class GNN_GraphSage_Layer(nn.Module):
    '''
        A single GraphSage Layer: Graph Sampling and Aggregate
    '''
    def __init__(self, input_dim, output_dim, Bias, normalize_graphsage, dropout, aggregation, concat):
        super(GNN_Batched_GraphSage_Layer, self).__init__()

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.Bias = Bias
        self.dropout = dropout
        self.normalize_graphsage = normalize_graphsage
        self.aggregation = aggregation
        self.concat = concat

        if self.concat:
            self.learnable_weights = nn.Linear(self.input_dim*2, self.output_dim, bias=self.Bias)
        else:
            self.learnable_weights = nn.Linear(self.input_dim, self.output_dim, bias=self.Bias)

        self.normalize = F.normalize


    def forward(self, new_features, tilda_adjacency_matrix):

        #new_features = new_features.to(torch.float32)
        new_features = new_features.type(torch.float32)
        tilda_adjacency_matrix = tilda_adjacency_matrix.type(torch.float32)



        if self.aggregation == 'mean':
            tilda_adjacency_matrix = tilda_adjacency_matrix / tilda_adjacency_matrix.sum(-2, keepdim=True)


        aggregated_neghborhood = torch.bmm(tilda_adjacency_matrix, new_features) # Y = A~ * X
        aggregated_neghborhood = torch.nan_to_num(aggregated_neghborhood, nan=0)

        if self.concat:
            aggregated_neghborhood = torch.cat((aggregated_neghborhood, new_features), 2)

        node_linear = self.learnable_weights(aggregated_neghborhood) # Y * W

        if self.normalize_graphsage:
            node_linear = self.normalize(node_linear, p=2, dim=2)



        return node_linear