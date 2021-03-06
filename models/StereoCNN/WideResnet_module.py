#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: zcy
# @Date:   2019-02-14 19:29:27
# @Last Modified by:   zcy
# @Last Modified time: 2019-02-16 11:18:59
import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from functools import partial

__all__ = ['WideResNet', 'WideBottleneck']


def conv3x3x3(in_planes, out_planes, stride=1):
    # 3x3x3 convolution with padding
    return nn.Conv3d(
        in_planes,
        out_planes,
        kernel_size=3,
        stride=stride,
        padding=1,
        bias=False)


def downsample_basic_block(x, planes, stride):
    out = F.avg_pool3d(x, kernel_size=1, stride=stride)
    zero_pads = torch.Tensor(
        out.size(0), planes - out.size(1), out.size(2), out.size(3),
        out.size(4)).zero_()
    if isinstance(out.data, torch.cuda.FloatTensor):
        zero_pads = zero_pads.cuda()

    out = torch.cat([out.data, zero_pads], dim=1)

    return out


class WideBottleneck(nn.Module):
    expansion = 2

    def __init__(self, inplanes, planes, stride=1, downsample=None):
        super(WideBottleneck, self).__init__()
        self.conv1 = nn.Conv3d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm3d(planes)
        self.conv2 = nn.Conv3d(
            planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm3d(planes)
        self.conv3 = nn.Conv3d(
            planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm3d(planes * self.expansion)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class WideResNet(nn.Module):

    def __init__(self,
                 block,
                 layers,
                 k=1,
                 shortcut_type='B',
                 n_classes=400,
                 in_channels=3):

        super(WideResNet, self).__init__()

        first_features = 64 if in_channels==3 else 32
        self.inplanes = first_features

        self.conv1 = nn.Conv3d(
            in_channels,
            first_features,
            kernel_size=7,
            stride=(1, 2, 2),
            padding=(3, 3, 3),
            bias=False)
        self.bn1 = nn.BatchNorm3d(first_features)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool3d(kernel_size=(3, 3, 3), stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64 * k, layers[0], shortcut_type)
        self.layer2 = self._make_layer(
            block, 128 * k, layers[1], shortcut_type, stride=2)
        self.layer3 = self._make_layer(
            block, 256 * k, layers[2], shortcut_type, stride=2)
        self.layer4 = self._make_layer(
            block, 512 * k, layers[3], shortcut_type, stride=2)

        # self.fc = nn.Sequential(
        #     # nn.Dropout(),
        #     nn.Linear(512 * k * block.expansion, n_classes),
        #     )
        self.fc = nn.Linear(512 * k * block.expansion, n_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                m.weight = nn.init.kaiming_normal_(m.weight, mode='fan_out')
            elif isinstance(m, nn.BatchNorm3d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, shortcut_type, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            if shortcut_type == 'A':
                downsample = partial(
                    downsample_basic_block,
                    planes=planes * block.expansion,
                    stride=stride)
            else:
                downsample = nn.Sequential(
                    nn.Conv3d(
                        self.inplanes,
                        planes * block.expansion,
                        kernel_size=1,
                        stride=stride,
                        bias=False), nn.BatchNorm3d(planes * block.expansion))

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        # x = self.avgpool(x)
        x = F.adaptive_avg_pool3d(x, (1, 1, 1))

        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x

def wideresnet50_3d(**kwargs):
    """Constructs a ResNet-50 model.
    """
    model = WideResNet(WideBottleneck, [3, 4, 6, 3], **kwargs)
    return model

if __name__ == '__main__':
    a = 64
    img_size=(a, a)
    model = wideresnet50_3d(n_classes=2, in_channels=1)
    x = torch.randn(3, 1, 22, img_size[0], img_size[1])
    # (BatchSize, channels, depth, h, w)
    y = model(x)
    torch.save(model.state_dict(), "m.pth")
    print(y.size())

