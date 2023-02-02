//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// TPU-MLIR is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//

#include "tpu_mlir/Conversion/TopToTpu/LoweringCV18xx.h"

namespace tpu_mlir {
namespace cv18xx {

void populateTopToTpuConversionPatterns(RewritePatternSet *patterns) {
  patterns->add<
      // clang-format off
      AbsLowering,
      AddLowering,
      AddConstLowering,
      AvgPoolLowering,
      CastLowering,
      ConcatLowering,
      ConvLowering,
      ClipLowering,
      CopyLowering,
      CscLowering,
      DeconvLowering,
      Depth2SpaceLowering,
      DetectionOutputLowering,
      DivLowering,
      ExpLowering,
      FrcnDetectionLowering,
      GatherLowering,
      GRULowering,
      HardSigmoidLowering,
      HardSwishLowering,
      InterpLowering,
      LayerNormLowering,
      LeakyReluLowering,
      LogLowering,
      LRNLowering,
      LSTMLowering,
      MatMulLowering,
      MaxLowering,
      MaxPoolLowering,
      MaxUnpoolLowering,
      MaxPoolWithMaskLowering,
      MinLowering,
      MishLowering,
      MulLowering,
      MulConstLowering,
      ReshapeLowering,
      PadLowering,
      PowLowering,
      PreprocessLowering,
      ProposalLowering,
      PermuteLowering,
      ROIPoolingLowering,
      RetinaFaceDetectionLowering,
      ReduceLowering,
      ReverseLowering,
      PReluLowering,
      PoolMaskLowering,
      ReluLowering,
      ReciprocalLowering,
      ScaleLowering,
      ScaleLutLowering,
      ShuffleChannelLowering,
      SigmoidLowering,
      SiLULowering,
      SliceLowering,
      SoftmaxLowering,
      SubLowering,
      SwapChannelLowering,
      TanhLowering,
      TileLowering,
      UpsampleLowering,
      YoloDetectionLowering
      // clang-format on
      >(patterns->getContext());
}
} // namespace cv18xx
} // namespace tpu_mlir
