import torch.nn as nn
from models.Unet_utils import *
from utils.init_weights import init_weights

class Unet_3D(nn.Module):
    def __init__(self, input_shape, output_shape, opt, num_classes = 2, is_conv=False):
        super(Unet_3D, self).__init__()
        
        self.in_channels = opt.n_channels
        self.is_batchnorm = opt.batchnorm
        self.feature_scale = opt.filter_scale
        self.norm_type = opt.norm_type
        self.is_conv = is_conv
        
        batchNormObject = lambda n_filters: nn.GroupNorm(opt.n_groups, n_filters) if self.norm_type != 'batch' else nn.BatchNorm3d(n_filters) 
    
  
        filters = [64, 128, 256, 512]
        filters = [int(x / self.feature_scale) for x in filters]

        self.maxpool = nn.MaxPool3d(kernel_size=2, stride=2)
        # downsampling
        self.conv_block_1 = R2CNN_block(self.in_channels, filters[0] // 2, filters[0], batchNormObject ,time=2,dr = opr.dr) 
        self.conv_block_2 = R2CNN_block(filters[0], filters[0], filters[1], batchNormObject ,time=2,dr = opr.dr) 
        self.conv_block_3 = R2CNN_block(filters[1], filters[1], filters[2], batchNormObject ,time=2,dr = opr.dr) 
        

        
        self.center_block = R2CNN_block(filters[2], filters[2], filters[3], batchNormObject ,time=2,dr =opr.dr) 
        self.gating = UnetGridGatingSignal3(filters[3], filters[3], (1, 1, 1), self.is_batchnorm,  batchNormObject)

        # upsampling
        self.up_concat3 = Up_Conv_3D(filters[3], filters[3], filters[2], block =R2CNN_block, batchNormObject=batchNormObject ,time=2,dr =opr.dr) 
        self.up_concat2 = Up_Conv_3D(filters[2], filters[2], filters[1], block =R2CNN_block, batchNormObject= batchNormObject ,time=2,dr =opr.dr) 
        self.up_concat1 = Up_Conv_3D(filters[1], filters[1], filters[0], block =R2CNN_block, batchNormObject=batchNormObject ,time=2,dr =opr.dr) 


        
         # attention blocks

        self.att1 = MultiAttentionBlock(in_size=filters[0], gating_size=filters[1],mid_size=filters[0], is_conv=self.is_conv)
        self.att2 = MultiAttentionBlock(in_size=filters[1], gating_size=filters[2],mid_size=filters[1], is_conv=self.is_conv)
        self.att3 = MultiAttentionBlock(in_size=filters[2], gating_size=filters[3],mid_size=filters[2], is_conv=self.is_conv)
       
       
        # final conv (without any concat)
        self.final = Output_block_binary(filters[0], 1)
        #self.final = Output_block(filters[0], num_classes, self.is_batchnorm)

         # initialise weights
        for m in self.modules():
            if isinstance(m, nn.Conv3d):
                init_weights(m, init_type='kaiming')
            elif isinstance(m, nn.BatchNorm3d):
                init_weights(m, init_type='kaiming')



    def forward(self, inputs):
        conv1 = self.conv_block_1(inputs)
        max_pool1 = self.maxpool(conv1)

        conv2 = self.conv_block_2(max_pool1)
        max_pool2 = self.maxpool(conv2)

        conv3 = self.conv_block_3(max_pool2)
        max_pool3 = self.maxpool(conv3)

     
        center_block = self.center_block(max_pool3)
        gating = self.gating(center_block)
        
        # decoder and attention mechanism

        g_3, att3 = self.att3(conv3, gating)
        up3 = self.up_concat3(g_3,center_block)
        g_2, att2 = self.att2(conv2, up3)
        up2 = self.up_concat2(g_2, up3)
        g_1, att1 = self.att1(conv1, up2)
        up1 = self.up_concat1(g_1, up2)

        outputs = self.final(up1)

        return outputs
