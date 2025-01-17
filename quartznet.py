# Adjusted for Vitis-AI-Quantizer

import glob
import os
import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

import argparse
from pytorch_nndct.apis import torch_quantizer, dump_xmodel
from utils.common import post_process_predictions, post_process_transcripts, word_error_rate, to_numpy
from utils.audio_preprocessing import AudioToMelSpectrogramPreprocessor
from utils.data_layer import AudioToTextDataLayer

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

parser = argparse.ArgumentParser()

parser.add_argument(
    '--data_dir',
    default="/path/to/manifest_json/",
    help='Data set directory, when quant_mode=calib, it is for calibration, while quant_mode=test it is for evaluation')
parser.add_argument(
    '--model_dir',
    default="/path/to/trained_pth_model/",
    help='Trained model file path.'
)
parser.add_argument(
    '--subset_len',
    default=None,
    type=int,
    help='subset_len to evaluate model, using the whole validation dataset if it is not set')
parser.add_argument(
    '--batch_size',
    default=32,
    type=int,
    help='input data batch size to evaluate model')
parser.add_argument('--quant_mode', 
    default='calib', 
    choices=['float', 'calib', 'test'], 
    help='quantization mode. 0: no quantization, evaluate float model, calib: quantize, test: evaluate quantized model')
parser.add_argument('--fast_finetune', 
    dest='fast_finetune',
    action='store_true',
    help='fast finetune model before calibration')
parser.add_argument('--deploy', 
    dest='deploy',
    action='store_true',
    help='export xmodel for deployment')
args, _ = parser.parse_known_args()

vocab = [" ", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z", "'"]

class Model(nn.Module):
  def __init__(self):
    super(Model, self).__init__()
    self._vars = nn.ParameterDict()
    self._regularizer_params = []
    for b in glob.glob(
        os.path.join(os.path.dirname(__file__), "variables", "*.npy")):
      v = torch.from_numpy(np.load(b))
      requires_grad = v.dtype.is_floating_point or v.dtype.is_complex
      self._vars[os.path.basename(b)[:-4]] = nn.Parameter(v, requires_grad=requires_grad)
    self.n_Conv_0 = nn.Conv1d(**{'groups': 64, 'dilation': [1], 'out_channels': 64, 'padding': [16], 'kernel_size': (33,), 'stride': [2], 'in_channels': 64, 'bias': False})
    self.n_Conv_0.weight.data = self._vars["encoder_encoder_0_mconv_0_conv_weight"]
    self.n_Conv_1 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 64, 'bias': True})
    self.n_Conv_1.weight.data = self._vars["t_1000"]
    self.n_Conv_1.bias.data = self._vars["t_1001"]
    self.n_Conv_3 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_3.weight.data = self._vars["encoder_encoder_1_mconv_0_conv_weight"]
    self.n_Conv_4 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_4.weight.data = self._vars["t_1003"]
    self.n_Conv_4.bias.data = self._vars["t_1004"]
    self.n_Conv_6 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_6.weight.data = self._vars["encoder_encoder_1_mconv_5_conv_weight"]
    self.n_Conv_7 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_7.weight.data = self._vars["t_1006"]
    self.n_Conv_7.bias.data = self._vars["t_1007"]
    self.n_Conv_9 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_9.weight.data = self._vars["encoder_encoder_1_mconv_10_conv_weight"]
    self.n_Conv_10 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_10.weight.data = self._vars["t_1009"]
    self.n_Conv_10.bias.data = self._vars["t_1010"]
    self.n_Conv_12 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_12.weight.data = self._vars["encoder_encoder_1_mconv_15_conv_weight"]
    self.n_Conv_13 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_13.weight.data = self._vars["t_1012"]
    self.n_Conv_13.bias.data = self._vars["t_1013"]
    self.n_Conv_15 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_15.weight.data = self._vars["encoder_encoder_1_mconv_20_conv_weight"]
    self.n_Conv_16 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_16.weight.data = self._vars["t_1015"]
    self.n_Conv_16.bias.data = self._vars["t_1016"]
    self.n_Conv_17 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_17.weight.data = self._vars["t_1018"]
    self.n_Conv_17.bias.data = self._vars["t_1019"]
    self.n_Conv_20 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_20.weight.data = self._vars["encoder_encoder_2_mconv_0_conv_weight"]
    self.n_Conv_21 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_21.weight.data = self._vars["t_1021"]
    self.n_Conv_21.bias.data = self._vars["t_1022"]
    self.n_Conv_23 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_23.weight.data = self._vars["encoder_encoder_2_mconv_5_conv_weight"]
    self.n_Conv_24 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_24.weight.data = self._vars["t_1024"]
    self.n_Conv_24.bias.data = self._vars["t_1025"]
    self.n_Conv_26 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_26.weight.data = self._vars["encoder_encoder_2_mconv_10_conv_weight"]
    self.n_Conv_27 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_27.weight.data = self._vars["t_1027"]
    self.n_Conv_27.bias.data = self._vars["t_1028"]
    self.n_Conv_29 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_29.weight.data = self._vars["encoder_encoder_2_mconv_15_conv_weight"]
    self.n_Conv_30 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_30.weight.data = self._vars["t_1030"]
    self.n_Conv_30.bias.data = self._vars["t_1031"]
    self.n_Conv_32 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_32.weight.data = self._vars["encoder_encoder_2_mconv_20_conv_weight"]
    self.n_Conv_33 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_33.weight.data = self._vars["t_1033"]
    self.n_Conv_33.bias.data = self._vars["t_1034"]
    self.n_Conv_34 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_34.weight.data = self._vars["t_1036"]
    self.n_Conv_34.bias.data = self._vars["t_1037"]
    self.n_Conv_37 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_37.weight.data = self._vars["encoder_encoder_3_mconv_0_conv_weight"]
    self.n_Conv_38 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_38.weight.data = self._vars["t_1039"]
    self.n_Conv_38.bias.data = self._vars["t_1040"]
    self.n_Conv_40 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_40.weight.data = self._vars["encoder_encoder_3_mconv_5_conv_weight"]
    self.n_Conv_41 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_41.weight.data = self._vars["t_1042"]
    self.n_Conv_41.bias.data = self._vars["t_1043"]
    self.n_Conv_43 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_43.weight.data = self._vars["encoder_encoder_3_mconv_10_conv_weight"]
    self.n_Conv_44 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_44.weight.data = self._vars["t_1045"]
    self.n_Conv_44.bias.data = self._vars["t_1046"]
    self.n_Conv_46 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_46.weight.data = self._vars["encoder_encoder_3_mconv_15_conv_weight"]
    self.n_Conv_47 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_47.weight.data = self._vars["t_1048"]
    self.n_Conv_47.bias.data = self._vars["t_1049"]
    self.n_Conv_49 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [16], 'kernel_size': (33,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_49.weight.data = self._vars["encoder_encoder_3_mconv_20_conv_weight"]
    self.n_Conv_50 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_50.weight.data = self._vars["t_1051"]
    self.n_Conv_50.bias.data = self._vars["t_1052"]
    self.n_Conv_51 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_51.weight.data = self._vars["t_1054"]
    self.n_Conv_51.bias.data = self._vars["t_1055"]
    self.n_Conv_54 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_54.weight.data = self._vars["encoder_encoder_4_mconv_0_conv_weight"]
    self.n_Conv_55 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_55.weight.data = self._vars["t_1057"]
    self.n_Conv_55.bias.data = self._vars["t_1058"]
    self.n_Conv_57 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_57.weight.data = self._vars["encoder_encoder_4_mconv_5_conv_weight"]
    self.n_Conv_58 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_58.weight.data = self._vars["t_1060"]
    self.n_Conv_58.bias.data = self._vars["t_1061"]
    self.n_Conv_60 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_60.weight.data = self._vars["encoder_encoder_4_mconv_10_conv_weight"]
    self.n_Conv_61 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_61.weight.data = self._vars["t_1063"]
    self.n_Conv_61.bias.data = self._vars["t_1064"]
    self.n_Conv_63 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_63.weight.data = self._vars["encoder_encoder_4_mconv_15_conv_weight"]
    self.n_Conv_64 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_64.weight.data = self._vars["t_1066"]
    self.n_Conv_64.bias.data = self._vars["t_1067"]
    self.n_Conv_66 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_66.weight.data = self._vars["encoder_encoder_4_mconv_20_conv_weight"]
    self.n_Conv_67 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_67.weight.data = self._vars["t_1069"]
    self.n_Conv_67.bias.data = self._vars["t_1070"]
    self.n_Conv_68 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_68.weight.data = self._vars["t_1072"]
    self.n_Conv_68.bias.data = self._vars["t_1073"]
    self.n_Conv_71 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_71.weight.data = self._vars["encoder_encoder_5_mconv_0_conv_weight"]
    self.n_Conv_72 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_72.weight.data = self._vars["t_1075"]
    self.n_Conv_72.bias.data = self._vars["t_1076"]
    self.n_Conv_74 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_74.weight.data = self._vars["encoder_encoder_5_mconv_5_conv_weight"]
    self.n_Conv_75 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_75.weight.data = self._vars["t_1078"]
    self.n_Conv_75.bias.data = self._vars["t_1079"]
    self.n_Conv_77 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_77.weight.data = self._vars["encoder_encoder_5_mconv_10_conv_weight"]
    self.n_Conv_78 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_78.weight.data = self._vars["t_1081"]
    self.n_Conv_78.bias.data = self._vars["t_1082"]
    self.n_Conv_80 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_80.weight.data = self._vars["encoder_encoder_5_mconv_15_conv_weight"]
    self.n_Conv_81 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_81.weight.data = self._vars["t_1084"]
    self.n_Conv_81.bias.data = self._vars["t_1085"]
    self.n_Conv_83 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_83.weight.data = self._vars["encoder_encoder_5_mconv_20_conv_weight"]
    self.n_Conv_84 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_84.weight.data = self._vars["t_1087"]
    self.n_Conv_84.bias.data = self._vars["t_1088"]
    self.n_Conv_85 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_85.weight.data = self._vars["t_1090"]
    self.n_Conv_85.bias.data = self._vars["t_1091"]
    self.n_Conv_88 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_88.weight.data = self._vars["encoder_encoder_6_mconv_0_conv_weight"]
    self.n_Conv_89 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_89.weight.data = self._vars["t_1093"]
    self.n_Conv_89.bias.data = self._vars["t_1094"]
    self.n_Conv_91 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_91.weight.data = self._vars["encoder_encoder_6_mconv_5_conv_weight"]
    self.n_Conv_92 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_92.weight.data = self._vars["t_1096"]
    self.n_Conv_92.bias.data = self._vars["t_1097"]
    self.n_Conv_94 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_94.weight.data = self._vars["encoder_encoder_6_mconv_10_conv_weight"]
    self.n_Conv_95 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_95.weight.data = self._vars["t_1099"]
    self.n_Conv_95.bias.data = self._vars["t_1100"]
    self.n_Conv_97 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_97.weight.data = self._vars["encoder_encoder_6_mconv_15_conv_weight"]
    self.n_Conv_98 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_98.weight.data = self._vars["t_1102"]
    self.n_Conv_98.bias.data = self._vars["t_1103"]
    self.n_Conv_100 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [19], 'kernel_size': (39,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_100.weight.data = self._vars["encoder_encoder_6_mconv_20_conv_weight"]
    self.n_Conv_101 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_101.weight.data = self._vars["t_1105"]
    self.n_Conv_101.bias.data = self._vars["t_1106"]
    self.n_Conv_102 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 256, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_102.weight.data = self._vars["t_1108"]
    self.n_Conv_102.bias.data = self._vars["t_1109"]
    self.n_Conv_105 = nn.Conv1d(**{'groups': 256, 'dilation': [1], 'out_channels': 256, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 256, 'bias': False})
    self.n_Conv_105.weight.data = self._vars["encoder_encoder_7_mconv_0_conv_weight"]
    self.n_Conv_106 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_106.weight.data = self._vars["t_1111"]
    self.n_Conv_106.bias.data = self._vars["t_1112"]
    self.n_Conv_108 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_108.weight.data = self._vars["encoder_encoder_7_mconv_5_conv_weight"]
    self.n_Conv_109 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_109.weight.data = self._vars["t_1114"]
    self.n_Conv_109.bias.data = self._vars["t_1115"]
    self.n_Conv_111 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_111.weight.data = self._vars["encoder_encoder_7_mconv_10_conv_weight"]
    self.n_Conv_112 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_112.weight.data = self._vars["t_1117"]
    self.n_Conv_112.bias.data = self._vars["t_1118"]
    self.n_Conv_114 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_114.weight.data = self._vars["encoder_encoder_7_mconv_15_conv_weight"]
    self.n_Conv_115 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_115.weight.data = self._vars["t_1120"]
    self.n_Conv_115.bias.data = self._vars["t_1121"]
    self.n_Conv_117 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_117.weight.data = self._vars["encoder_encoder_7_mconv_20_conv_weight"]
    self.n_Conv_118 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_118.weight.data = self._vars["t_1123"]
    self.n_Conv_118.bias.data = self._vars["t_1124"]
    self.n_Conv_119 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 256, 'bias': True})
    self.n_Conv_119.weight.data = self._vars["t_1126"]
    self.n_Conv_119.bias.data = self._vars["t_1127"]
    self.n_Conv_122 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_122.weight.data = self._vars["encoder_encoder_8_mconv_0_conv_weight"]
    self.n_Conv_123 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_123.weight.data = self._vars["t_1129"]
    self.n_Conv_123.bias.data = self._vars["t_1130"]
    self.n_Conv_125 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_125.weight.data = self._vars["encoder_encoder_8_mconv_5_conv_weight"]
    self.n_Conv_126 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_126.weight.data = self._vars["t_1132"]
    self.n_Conv_126.bias.data = self._vars["t_1133"]
    self.n_Conv_128 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_128.weight.data = self._vars["encoder_encoder_8_mconv_10_conv_weight"]
    self.n_Conv_129 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_129.weight.data = self._vars["t_1135"]
    self.n_Conv_129.bias.data = self._vars["t_1136"]
    self.n_Conv_131 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_131.weight.data = self._vars["encoder_encoder_8_mconv_15_conv_weight"]
    self.n_Conv_132 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_132.weight.data = self._vars["t_1138"]
    self.n_Conv_132.bias.data = self._vars["t_1139"]
    self.n_Conv_134 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_134.weight.data = self._vars["encoder_encoder_8_mconv_20_conv_weight"]
    self.n_Conv_135 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_135.weight.data = self._vars["t_1141"]
    self.n_Conv_135.bias.data = self._vars["t_1142"]
    self.n_Conv_136 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_136.weight.data = self._vars["t_1144"]
    self.n_Conv_136.bias.data = self._vars["t_1145"]
    self.n_Conv_139 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_139.weight.data = self._vars["encoder_encoder_9_mconv_0_conv_weight"]
    self.n_Conv_140 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_140.weight.data = self._vars["t_1147"]
    self.n_Conv_140.bias.data = self._vars["t_1148"]
    self.n_Conv_142 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_142.weight.data = self._vars["encoder_encoder_9_mconv_5_conv_weight"]
    self.n_Conv_143 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_143.weight.data = self._vars["t_1150"]
    self.n_Conv_143.bias.data = self._vars["t_1151"]
    self.n_Conv_145 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_145.weight.data = self._vars["encoder_encoder_9_mconv_10_conv_weight"]
    self.n_Conv_146 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_146.weight.data = self._vars["t_1153"]
    self.n_Conv_146.bias.data = self._vars["t_1154"]
    self.n_Conv_148 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_148.weight.data = self._vars["encoder_encoder_9_mconv_15_conv_weight"]
    self.n_Conv_149 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_149.weight.data = self._vars["t_1156"]
    self.n_Conv_149.bias.data = self._vars["t_1157"]
    self.n_Conv_151 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [25], 'kernel_size': (51,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_151.weight.data = self._vars["encoder_encoder_9_mconv_20_conv_weight"]
    self.n_Conv_152 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_152.weight.data = self._vars["t_1159"]
    self.n_Conv_152.bias.data = self._vars["t_1160"]
    self.n_Conv_153 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_153.weight.data = self._vars["t_1162"]
    self.n_Conv_153.bias.data = self._vars["t_1163"]
    self.n_Conv_156 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_156.weight.data = self._vars["encoder_encoder_10_mconv_0_conv_weight"]
    self.n_Conv_157 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_157.weight.data = self._vars["t_1165"]
    self.n_Conv_157.bias.data = self._vars["t_1166"]
    self.n_Conv_159 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_159.weight.data = self._vars["encoder_encoder_10_mconv_5_conv_weight"]
    self.n_Conv_160 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_160.weight.data = self._vars["t_1168"]
    self.n_Conv_160.bias.data = self._vars["t_1169"]
    self.n_Conv_162 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_162.weight.data = self._vars["encoder_encoder_10_mconv_10_conv_weight"]
    self.n_Conv_163 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_163.weight.data = self._vars["t_1171"]
    self.n_Conv_163.bias.data = self._vars["t_1172"]
    self.n_Conv_165 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_165.weight.data = self._vars["encoder_encoder_10_mconv_15_conv_weight"]
    self.n_Conv_166 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_166.weight.data = self._vars["t_1174"]
    self.n_Conv_166.bias.data = self._vars["t_1175"]
    self.n_Conv_168 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_168.weight.data = self._vars["encoder_encoder_10_mconv_20_conv_weight"]
    self.n_Conv_169 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_169.weight.data = self._vars["t_1177"]
    self.n_Conv_169.bias.data = self._vars["t_1178"]
    self.n_Conv_170 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_170.weight.data = self._vars["t_1180"]
    self.n_Conv_170.bias.data = self._vars["t_1181"]
    self.n_Conv_173 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_173.weight.data = self._vars["encoder_encoder_11_mconv_0_conv_weight"]
    self.n_Conv_174 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_174.weight.data = self._vars["t_1183"]
    self.n_Conv_174.bias.data = self._vars["t_1184"]
    self.n_Conv_176 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_176.weight.data = self._vars["encoder_encoder_11_mconv_5_conv_weight"]
    self.n_Conv_177 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_177.weight.data = self._vars["t_1186"]
    self.n_Conv_177.bias.data = self._vars["t_1187"]
    self.n_Conv_179 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_179.weight.data = self._vars["encoder_encoder_11_mconv_10_conv_weight"]
    self.n_Conv_180 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_180.weight.data = self._vars["t_1189"]
    self.n_Conv_180.bias.data = self._vars["t_1190"]
    self.n_Conv_182 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_182.weight.data = self._vars["encoder_encoder_11_mconv_15_conv_weight"]
    self.n_Conv_183 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_183.weight.data = self._vars["t_1192"]
    self.n_Conv_183.bias.data = self._vars["t_1193"]
    self.n_Conv_185 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_185.weight.data = self._vars["encoder_encoder_11_mconv_20_conv_weight"]
    self.n_Conv_186 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_186.weight.data = self._vars["t_1195"]
    self.n_Conv_186.bias.data = self._vars["t_1196"]
    self.n_Conv_187 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_187.weight.data = self._vars["t_1198"]
    self.n_Conv_187.bias.data = self._vars["t_1199"]
    self.n_Conv_190 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_190.weight.data = self._vars["encoder_encoder_12_mconv_0_conv_weight"]
    self.n_Conv_191 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_191.weight.data = self._vars["t_1201"]
    self.n_Conv_191.bias.data = self._vars["t_1202"]
    self.n_Conv_193 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_193.weight.data = self._vars["encoder_encoder_12_mconv_5_conv_weight"]
    self.n_Conv_194 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_194.weight.data = self._vars["t_1204"]
    self.n_Conv_194.bias.data = self._vars["t_1205"]
    self.n_Conv_196 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_196.weight.data = self._vars["encoder_encoder_12_mconv_10_conv_weight"]
    self.n_Conv_197 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_197.weight.data = self._vars["t_1207"]
    self.n_Conv_197.bias.data = self._vars["t_1208"]
    self.n_Conv_199 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_199.weight.data = self._vars["encoder_encoder_12_mconv_15_conv_weight"]
    self.n_Conv_200 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_200.weight.data = self._vars["t_1210"]
    self.n_Conv_200.bias.data = self._vars["t_1211"]
    self.n_Conv_202 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [31], 'kernel_size': (63,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_202.weight.data = self._vars["encoder_encoder_12_mconv_20_conv_weight"]
    self.n_Conv_203 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_203.weight.data = self._vars["t_1213"]
    self.n_Conv_203.bias.data = self._vars["t_1214"]
    self.n_Conv_204 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_204.weight.data = self._vars["t_1216"]
    self.n_Conv_204.bias.data = self._vars["t_1217"]
    self.n_Conv_207 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_207.weight.data = self._vars["encoder_encoder_13_mconv_0_conv_weight"]
    self.n_Conv_208 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_208.weight.data = self._vars["t_1219"]
    self.n_Conv_208.bias.data = self._vars["t_1220"]
    self.n_Conv_210 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_210.weight.data = self._vars["encoder_encoder_13_mconv_5_conv_weight"]
    self.n_Conv_211 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_211.weight.data = self._vars["t_1222"]
    self.n_Conv_211.bias.data = self._vars["t_1223"]
    self.n_Conv_213 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_213.weight.data = self._vars["encoder_encoder_13_mconv_10_conv_weight"]
    self.n_Conv_214 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_214.weight.data = self._vars["t_1225"]
    self.n_Conv_214.bias.data = self._vars["t_1226"]
    self.n_Conv_216 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_216.weight.data = self._vars["encoder_encoder_13_mconv_15_conv_weight"]
    self.n_Conv_217 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_217.weight.data = self._vars["t_1228"]
    self.n_Conv_217.bias.data = self._vars["t_1229"]
    self.n_Conv_219 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_219.weight.data = self._vars["encoder_encoder_13_mconv_20_conv_weight"]
    self.n_Conv_220 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_220.weight.data = self._vars["t_1231"]
    self.n_Conv_220.bias.data = self._vars["t_1232"]
    self.n_Conv_221 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_221.weight.data = self._vars["t_1234"]
    self.n_Conv_221.bias.data = self._vars["t_1235"]
    self.n_Conv_224 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_224.weight.data = self._vars["encoder_encoder_14_mconv_0_conv_weight"]
    self.n_Conv_225 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_225.weight.data = self._vars["t_1237"]
    self.n_Conv_225.bias.data = self._vars["t_1238"]
    self.n_Conv_227 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_227.weight.data = self._vars["encoder_encoder_14_mconv_5_conv_weight"]
    self.n_Conv_228 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_228.weight.data = self._vars["t_1240"]
    self.n_Conv_228.bias.data = self._vars["t_1241"]
    self.n_Conv_230 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_230.weight.data = self._vars["encoder_encoder_14_mconv_10_conv_weight"]
    self.n_Conv_231 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_231.weight.data = self._vars["t_1243"]
    self.n_Conv_231.bias.data = self._vars["t_1244"]
    self.n_Conv_233 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_233.weight.data = self._vars["encoder_encoder_14_mconv_15_conv_weight"]
    self.n_Conv_234 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_234.weight.data = self._vars["t_1246"]
    self.n_Conv_234.bias.data = self._vars["t_1247"]
    self.n_Conv_236 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_236.weight.data = self._vars["encoder_encoder_14_mconv_20_conv_weight"]
    self.n_Conv_237 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_237.weight.data = self._vars["t_1249"]
    self.n_Conv_237.bias.data = self._vars["t_1250"]
    self.n_Conv_238 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_238.weight.data = self._vars["t_1252"]
    self.n_Conv_238.bias.data = self._vars["t_1253"]
    self.n_Conv_241 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_241.weight.data = self._vars["encoder_encoder_15_mconv_0_conv_weight"]
    self.n_Conv_242 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_242.weight.data = self._vars["t_1255"]
    self.n_Conv_242.bias.data = self._vars["t_1256"]
    self.n_Conv_244 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_244.weight.data = self._vars["encoder_encoder_15_mconv_5_conv_weight"]
    self.n_Conv_245 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_245.weight.data = self._vars["t_1258"]
    self.n_Conv_245.bias.data = self._vars["t_1259"]
    self.n_Conv_247 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_247.weight.data = self._vars["encoder_encoder_15_mconv_10_conv_weight"]
    self.n_Conv_248 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_248.weight.data = self._vars["t_1261"]
    self.n_Conv_248.bias.data = self._vars["t_1262"]
    self.n_Conv_250 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_250.weight.data = self._vars["encoder_encoder_15_mconv_15_conv_weight"]
    self.n_Conv_251 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_251.weight.data = self._vars["t_1264"]
    self.n_Conv_251.bias.data = self._vars["t_1265"]
    self.n_Conv_253 = nn.Conv1d(**{'groups': 512, 'dilation': [1], 'out_channels': 512, 'padding': [37], 'kernel_size': (75,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_253.weight.data = self._vars["encoder_encoder_15_mconv_20_conv_weight"]
    self.n_Conv_254 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_254.weight.data = self._vars["t_1267"]
    self.n_Conv_254.bias.data = self._vars["t_1268"]
    self.n_Conv_255 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_255.weight.data = self._vars["t_1270"]
    self.n_Conv_255.bias.data = self._vars["t_1271"]
    self.n_Conv_258 = nn.Conv1d(**{'groups': 512, 'dilation': [2], 'out_channels': 512, 'padding': [86], 'kernel_size': (87,), 'stride': [1], 'in_channels': 512, 'bias': False})
    self.n_Conv_258.weight.data = self._vars["encoder_encoder_16_mconv_0_conv_weight"]
    self.n_Conv_259 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 512, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_259.weight.data = self._vars["t_1273"]
    self.n_Conv_259.bias.data = self._vars["t_1274"]
    self.n_Conv_261 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 1024, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 512, 'bias': True})
    self.n_Conv_261.weight.data = self._vars["t_1276"]
    self.n_Conv_261.bias.data = self._vars["t_1277"]
    self.n_Conv_263 = nn.Conv1d(**{'groups': 1, 'dilation': [1], 'out_channels': 29, 'padding': [0], 'kernel_size': (1,), 'stride': [1], 'in_channels': 1024, 'bias': True})
    self.n_Conv_263.weight.data = self._vars["decoder_decoder_layers_0_weight"]
    self.n_Conv_263.bias.data = self._vars["decoder_decoder_layers_0_bias"]

  def forward(self, *inputs):
    audio_signal, = inputs
    t_640 = self.n_Conv_0(audio_signal)
    t_999 = self.n_Conv_1(t_640)
    t_643 = F.relu(t_999)
    t_644 = self.n_Conv_3(t_643)
    t_1002 = self.n_Conv_4(t_644)
    t_647 = F.relu(t_1002)
    t_648 = self.n_Conv_6(t_647)
    t_1005 = self.n_Conv_7(t_648)
    t_651 = F.relu(t_1005)
    t_652 = self.n_Conv_9(t_651)
    t_1008 = self.n_Conv_10(t_652)
    t_655 = F.relu(t_1008)
    t_656 = self.n_Conv_12(t_655)
    t_1011 = self.n_Conv_13(t_656)
    t_659 = F.relu(t_1011)
    t_660 = self.n_Conv_15(t_659)
    t_1014 = self.n_Conv_16(t_660)
    t_1017 = self.n_Conv_17(t_643)
    t_665 = torch.add(t_1014, t_1017)
    t_666 = F.relu(t_665)
    t_667 = self.n_Conv_20(t_666)
    t_1020 = self.n_Conv_21(t_667)
    t_670 = F.relu(t_1020)
    t_671 = self.n_Conv_23(t_670)
    t_1023 = self.n_Conv_24(t_671)
    t_674 = F.relu(t_1023)
    t_675 = self.n_Conv_26(t_674)
    t_1026 = self.n_Conv_27(t_675)
    t_678 = F.relu(t_1026)
    t_679 = self.n_Conv_29(t_678)
    t_1029 = self.n_Conv_30(t_679)
    t_682 = F.relu(t_1029)
    t_683 = self.n_Conv_32(t_682)
    t_1032 = self.n_Conv_33(t_683)
    t_1035 = self.n_Conv_34(t_666)
    t_688 = torch.add(t_1032, t_1035)
    t_689 = F.relu(t_688)
    t_690 = self.n_Conv_37(t_689)
    t_1038 = self.n_Conv_38(t_690)
    t_693 = F.relu(t_1038)
    t_694 = self.n_Conv_40(t_693)
    t_1041 = self.n_Conv_41(t_694)
    t_697 = F.relu(t_1041)
    t_698 = self.n_Conv_43(t_697)
    t_1044 = self.n_Conv_44(t_698)
    t_701 = F.relu(t_1044)
    t_702 = self.n_Conv_46(t_701)
    t_1047 = self.n_Conv_47(t_702)
    t_705 = F.relu(t_1047)
    t_706 = self.n_Conv_49(t_705)
    t_1050 = self.n_Conv_50(t_706)
    t_1053 = self.n_Conv_51(t_689)
    t_711 = torch.add(t_1050, t_1053)
    t_712 = F.relu(t_711)
    t_713 = self.n_Conv_54(t_712)
    t_1056 = self.n_Conv_55(t_713)
    t_716 = F.relu(t_1056)
    t_717 = self.n_Conv_57(t_716)
    t_1059 = self.n_Conv_58(t_717)
    t_720 = F.relu(t_1059)
    t_721 = self.n_Conv_60(t_720)
    t_1062 = self.n_Conv_61(t_721)
    t_724 = F.relu(t_1062)
    t_725 = self.n_Conv_63(t_724)
    t_1065 = self.n_Conv_64(t_725)
    t_728 = F.relu(t_1065)
    t_729 = self.n_Conv_66(t_728)
    t_1068 = self.n_Conv_67(t_729)
    t_1071 = self.n_Conv_68(t_712)
    t_734 = torch.add(t_1068, t_1071)
    t_735 = F.relu(t_734)
    t_736 = self.n_Conv_71(t_735)
    t_1074 = self.n_Conv_72(t_736)
    t_739 = F.relu(t_1074)
    t_740 = self.n_Conv_74(t_739)
    t_1077 = self.n_Conv_75(t_740)
    t_743 = F.relu(t_1077)
    t_744 = self.n_Conv_77(t_743)
    t_1080 = self.n_Conv_78(t_744)
    t_747 = F.relu(t_1080)
    t_748 = self.n_Conv_80(t_747)
    t_1083 = self.n_Conv_81(t_748)
    t_751 = F.relu(t_1083)
    t_752 = self.n_Conv_83(t_751)
    t_1086 = self.n_Conv_84(t_752)
    t_1089 = self.n_Conv_85(t_735)
    t_757 = torch.add(t_1086, t_1089)
    t_758 = F.relu(t_757)
    t_759 = self.n_Conv_88(t_758)
    t_1092 = self.n_Conv_89(t_759)
    t_762 = F.relu(t_1092)
    t_763 = self.n_Conv_91(t_762)
    t_1095 = self.n_Conv_92(t_763)
    t_766 = F.relu(t_1095)
    t_767 = self.n_Conv_94(t_766)
    t_1098 = self.n_Conv_95(t_767)
    t_770 = F.relu(t_1098)
    t_771 = self.n_Conv_97(t_770)
    t_1101 = self.n_Conv_98(t_771)
    t_774 = F.relu(t_1101)
    t_775 = self.n_Conv_100(t_774)
    t_1104 = self.n_Conv_101(t_775)
    t_1107 = self.n_Conv_102(t_758)
    t_780 = torch.add(t_1104, t_1107)
    t_781 = F.relu(t_780)
    t_782 = self.n_Conv_105(t_781)
    t_1110 = self.n_Conv_106(t_782)
    t_785 = F.relu(t_1110)
    t_786 = self.n_Conv_108(t_785)
    t_1113 = self.n_Conv_109(t_786)
    t_789 = F.relu(t_1113)
    t_790 = self.n_Conv_111(t_789)
    t_1116 = self.n_Conv_112(t_790)
    t_793 = F.relu(t_1116)
    t_794 = self.n_Conv_114(t_793)
    t_1119 = self.n_Conv_115(t_794)
    t_797 = F.relu(t_1119)
    t_798 = self.n_Conv_117(t_797)
    t_1122 = self.n_Conv_118(t_798)
    t_1125 = self.n_Conv_119(t_781)
    t_803 = torch.add(t_1122, t_1125)
    t_804 = F.relu(t_803)
    t_805 = self.n_Conv_122(t_804)
    t_1128 = self.n_Conv_123(t_805)
    t_808 = F.relu(t_1128)
    t_809 = self.n_Conv_125(t_808)
    t_1131 = self.n_Conv_126(t_809)
    t_812 = F.relu(t_1131)
    t_813 = self.n_Conv_128(t_812)
    t_1134 = self.n_Conv_129(t_813)
    t_816 = F.relu(t_1134)
    t_817 = self.n_Conv_131(t_816)
    t_1137 = self.n_Conv_132(t_817)
    t_820 = F.relu(t_1137)
    t_821 = self.n_Conv_134(t_820)
    t_1140 = self.n_Conv_135(t_821)
    t_1143 = self.n_Conv_136(t_804)
    t_826 = torch.add(t_1140, t_1143)
    t_827 = F.relu(t_826)
    t_828 = self.n_Conv_139(t_827)
    t_1146 = self.n_Conv_140(t_828)
    t_831 = F.relu(t_1146)
    t_832 = self.n_Conv_142(t_831)
    t_1149 = self.n_Conv_143(t_832)
    t_835 = F.relu(t_1149)
    t_836 = self.n_Conv_145(t_835)
    t_1152 = self.n_Conv_146(t_836)
    t_839 = F.relu(t_1152)
    t_840 = self.n_Conv_148(t_839)
    t_1155 = self.n_Conv_149(t_840)
    t_843 = F.relu(t_1155)
    t_844 = self.n_Conv_151(t_843)
    t_1158 = self.n_Conv_152(t_844)
    t_1161 = self.n_Conv_153(t_827)
    t_849 = torch.add(t_1158, t_1161)
    t_850 = F.relu(t_849)
    t_851 = self.n_Conv_156(t_850)
    t_1164 = self.n_Conv_157(t_851)
    t_854 = F.relu(t_1164)
    t_855 = self.n_Conv_159(t_854)
    t_1167 = self.n_Conv_160(t_855)
    t_858 = F.relu(t_1167)
    t_859 = self.n_Conv_162(t_858)
    t_1170 = self.n_Conv_163(t_859)
    t_862 = F.relu(t_1170)
    t_863 = self.n_Conv_165(t_862)
    t_1173 = self.n_Conv_166(t_863)
    t_866 = F.relu(t_1173)
    t_867 = self.n_Conv_168(t_866)
    t_1176 = self.n_Conv_169(t_867)
    t_1179 = self.n_Conv_170(t_850)
    t_872 = torch.add(t_1176, t_1179)
    t_873 = F.relu(t_872)
    t_874 = self.n_Conv_173(t_873)
    t_1182 = self.n_Conv_174(t_874)
    t_877 = F.relu(t_1182)
    t_878 = self.n_Conv_176(t_877)
    t_1185 = self.n_Conv_177(t_878)
    t_881 = F.relu(t_1185)
    t_882 = self.n_Conv_179(t_881)
    t_1188 = self.n_Conv_180(t_882)
    t_885 = F.relu(t_1188)
    t_886 = self.n_Conv_182(t_885)
    t_1191 = self.n_Conv_183(t_886)
    t_889 = F.relu(t_1191)
    t_890 = self.n_Conv_185(t_889)
    t_1194 = self.n_Conv_186(t_890)
    t_1197 = self.n_Conv_187(t_873)
    t_895 = torch.add(t_1194, t_1197)
    t_896 = F.relu(t_895)
    t_897 = self.n_Conv_190(t_896)
    t_1200 = self.n_Conv_191(t_897)
    t_900 = F.relu(t_1200)
    t_901 = self.n_Conv_193(t_900)
    t_1203 = self.n_Conv_194(t_901)
    t_904 = F.relu(t_1203)
    t_905 = self.n_Conv_196(t_904)
    t_1206 = self.n_Conv_197(t_905)
    t_908 = F.relu(t_1206)
    t_909 = self.n_Conv_199(t_908)
    t_1209 = self.n_Conv_200(t_909)
    t_912 = F.relu(t_1209)
    t_913 = self.n_Conv_202(t_912)
    t_1212 = self.n_Conv_203(t_913)
    t_1215 = self.n_Conv_204(t_896)
    t_918 = torch.add(t_1212, t_1215)
    t_919 = F.relu(t_918)
    t_920 = self.n_Conv_207(t_919)
    t_1218 = self.n_Conv_208(t_920)
    t_923 = F.relu(t_1218)
    t_924 = self.n_Conv_210(t_923)
    t_1221 = self.n_Conv_211(t_924)
    t_927 = F.relu(t_1221)
    t_928 = self.n_Conv_213(t_927)
    t_1224 = self.n_Conv_214(t_928)
    t_931 = F.relu(t_1224)
    t_932 = self.n_Conv_216(t_931)
    t_1227 = self.n_Conv_217(t_932)
    t_935 = F.relu(t_1227)
    t_936 = self.n_Conv_219(t_935)
    t_1230 = self.n_Conv_220(t_936)
    t_1233 = self.n_Conv_221(t_919)
    t_941 = torch.add(t_1230, t_1233)
    t_942 = F.relu(t_941)
    t_943 = self.n_Conv_224(t_942)
    t_1236 = self.n_Conv_225(t_943)
    t_946 = F.relu(t_1236)
    t_947 = self.n_Conv_227(t_946)
    t_1239 = self.n_Conv_228(t_947)
    t_950 = F.relu(t_1239)
    t_951 = self.n_Conv_230(t_950)
    t_1242 = self.n_Conv_231(t_951)
    t_954 = F.relu(t_1242)
    t_955 = self.n_Conv_233(t_954)
    t_1245 = self.n_Conv_234(t_955)
    t_958 = F.relu(t_1245)
    t_959 = self.n_Conv_236(t_958)
    t_1248 = self.n_Conv_237(t_959)
    t_1251 = self.n_Conv_238(t_942)
    t_964 = torch.add(t_1248, t_1251)
    t_965 = F.relu(t_964)
    t_966 = self.n_Conv_241(t_965)
    t_1254 = self.n_Conv_242(t_966)
    t_969 = F.relu(t_1254)
    t_970 = self.n_Conv_244(t_969)
    t_1257 = self.n_Conv_245(t_970)
    t_973 = F.relu(t_1257)
    t_974 = self.n_Conv_247(t_973)
    t_1260 = self.n_Conv_248(t_974)
    t_977 = F.relu(t_1260)
    t_978 = self.n_Conv_250(t_977)
    t_1263 = self.n_Conv_251(t_978)
    t_981 = F.relu(t_1263)
    t_982 = self.n_Conv_253(t_981)
    t_1266 = self.n_Conv_254(t_982)
    t_1269 = self.n_Conv_255(t_965)
    t_987 = torch.add(t_1266, t_1269)
    t_988 = F.relu(t_987)
    t_989 = self.n_Conv_258(t_988)
    t_1272 = self.n_Conv_259(t_989)
    t_992 = F.relu(t_1272)
    t_1275 = self.n_Conv_261(t_992)
    t_995 = F.relu(t_1275)
    t_996 = self.n_Conv_263(t_995)
    t_997 = t_996.permute(*[0, 2, 1])
    logprobs = F.softmax(t_997, **{'dim': 2})
    return logprobs

  def compatible_auto_pad(self, input, kernel_spatial_shape, nn_mod, auto_pad=None, **kwargs):
    input_spatial_shape = input.shape[2:]
    d = len(input_spatial_shape)
    strides = nn_mod.stride
    dilations = nn_mod.dilation
    output_spatial_shape = [math.ceil(float(l) / float(r)) for l, r in zip(input.shape[2:], strides)]
    pt_padding = [0] * 2 * d
    pad_shape = [0] * d
    for i in range(d):
      pad_shape[i] = (output_spatial_shape[i] - 1) * strides[i] + ((kernel_spatial_shape[i] - 1) * dilations[i] + 1) - input_spatial_shape[i]
      mean = pad_shape[i] // 2
      if auto_pad == b"SAME_UPPER":
        l, r = pad_shape[i] - mean, mean
      else:
        l, r = mean, pad_shape[i] - mean
      pt_padding.insert(0, r)
      pt_padding.insert(0, l)
    return F.pad(input, pt_padding)

def accuracy(predictions, transcripts, transcripts_len):
  """Computes word error rate"""
  # Map characters
  greedy_hypotheses = post_process_predictions(predictions, vocab)
  references = post_process_transcripts(transcripts, transcripts_len, vocab)
  # Caculate word error rate and time cost
  wer = word_error_rate(hypotheses=greedy_hypotheses, references=references)
  return 1 - wer

@torch.no_grad()
def evaluate(model, val_data):
  model.eval()
  model = model.to(device)
  data_layer = AudioToTextDataLayer(
      manifest_filepath=val_data,
      sample_rate=16000,
      labels=vocab,
      batch_size=32,
      shuffle=False,
      drop_last=True)
  preprocessor = AudioToMelSpectrogramPreprocessor(sample_rate=16000) 
  predictions = []
  transcripts = []
  transcripts_len = []
  for i, test_batch in enumerate(data_layer.data_iterator):
      # Get audio [1, n], audio length n, transcript and transcript length
      audio_signal_e1, a_sig_length_e1, transcript_e1, transcript_len_e1 = test_batch

      # Get 64d MFCC features and accumulate time
      processed_signal = preprocessor.get_features(audio_signal_e1, a_sig_length_e1)

      # Inference and accumulate time. Input shape: [Batch_size, 64, Timesteps]
      prob = model(processed_signal)
      ologits = torch.log(prob)
      alogits = np.asarray(ologits)
      logits = torch.from_numpy(alogits[0])
      predictions_e1 = logits.argmax(dim=-1, keepdim=False)
      transcript_e1 = torch.from_numpy(np.asarray(test_batch[2])) 
      transcript_len_e1 = torch.from_numpy(np.asarray(test_batch[1])) 

      # Save results
      predictions.append(predictions_e1)
      transcripts.append(transcript_e1)
      transcripts_len.append(transcript_len_e1)
  acc = accuracy(predictions, transcripts, transcripts_len)
  return acc, 1 - acc

def quantization(title='optimize',
                 model_name='', 
                 file_path=''): 

  data_dir = args.data_dir
  quant_mode = args.quant_mode
  finetune = args.fast_finetune
  deploy = args.deploy
  batch_size = args.batch_size
  subset_len = args.subset_len
  if quant_mode != 'test' and deploy:
    deploy = False
    print(r'Warning: Exporting xmodel needs to be done in quantization test mode, turn off it in this running!')
  if deploy and (batch_size != 1 or subset_len != 1):
    print(r'Warning: Exporting xmodel needs batch size to be 1 and only 1 iteration of inference, change them automatically!')
    batch_size = 1
    subset_len = 1

  model = Model()
  #model.load_state_dict(torch.load(file_path))

  input = torch.randn([batch_size, 64, 256])
  if quant_mode == 'float':
    quant_model = model
  else:
    ## new api
    ####################################################################################
    quantizer = torch_quantizer(
        quant_mode, model, (input), device=device)

    quant_model = quantizer.quant_model
    #####################################################################################

  # fast finetune model or load finetuned parameter before test
  if finetune == True:

      if quant_mode == 'calib':
        quantizer.fast_finetune(evaluate, (quant_model, data_dir))
      elif quant_mode == 'test':
        quantizer.load_ft_param()
   
  # record  modules float model accuracy
  # add modules float model accuracy here

  #register_modification_hooks(model_gen, train=False)
  acc, wer = evaluate(quant_model, data_dir)

  # logging accuracy
  print('wer: %g' % (wer))

  # handle quantization result
  if quant_mode == 'calib':
    quantizer.export_quant_config()
  if deploy:
    quantizer.export_xmodel(deploy_check=False)

if __name__ == '__main__':
  model = Model()
  input = torch.randn([args.batch_size, 64, 256])
  quant_mode = args.quant_mode
  deploy = args.deploy
  quantizer = torch_quantizer(quant_mode, model, (input))
  quant_model = quantizer.quant_model
  acc, wer = evaluate(quant_model, args.data_dir)
  if quant_mode == 'calib':
    quantizer.export_quant_config()
  if deploy:
    quantizer.export_xmodel()
