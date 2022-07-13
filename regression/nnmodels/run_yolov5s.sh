#!/bin/bash
set -ex

mkdir -p yolov5s
pushd yolov5s

model_transform.py \
    --model_name yolov5s \
    --model_def  ${NNMODELS_PATH}/onnx_models/yolov5s.onnx \
    --mean 0.0,0.0,0.0 \
    --scale 0.0039216,0.0039216,0.0039216 \
    --keep_aspect_ratio \
    --output_names 170 \
    --test_input ${REGRESSION_PATH}/image/dog.jpg \
    --test_result yolov5s_top_outputs.npz \
    --mlir yolov5s.mlir

# model_transform.py \
#     --model_name yolov5s \
#     --model_def  ${NNMODELS_PATH}/onnx_models/yolov5s.onnx \
#     --input_shapes [[1,3,640,640]] \
#     --output_names 397,458,519 \
#     --mlir yolov5s.mlir

#########################
# deploy to float bmodel
#########################
model_deploy.py \
  --mlir yolov5s.mlir \
  --quantize F32 \
  --chip bm1684x \
  --test_input yolov5s_in_f32.npz \
  --test_reference yolov5s_top_outputs.npz \
  --tolerance 0.99,0.99 \
  --model yolov5s_1684x_f32.bmodel


#########################
# deploy to int8 bmodel
#########################
run_calibration.py yolov5s.mlir \
    --dataset $REGRESSION_PATH/image \
    --input_num 2 \
    -o yolov5s_cali_table

# to symmetric
model_deploy.py \
  --mlir yolov5s.mlir \
  --quantize INT8 \
  --calibration_table yolov5s_cali_table \
  --chip bm1684x \
  --test_input yolov5s_in_f32.npz \
  --test_reference yolov5s_top_outputs.npz \
  --tolerance 0.96,0.74 \
  --correctness 0.99,0.90 \
  --model yolov5s_1684x_int8_sym.bmodel

# to asymmetric
model_deploy.py \
  --mlir yolov5s.mlir \
  --quantize INT8 \
  --asymmetric \
  --calibration_table yolov5s_cali_table \
  --chip bm1684x \
  --test_input yolov5s_in_f32.npz \
  --test_reference yolov5s_top_outputs.npz \
  --tolerance 0.98,0.82 \
  --correctness 0.99,0.93 \
  --model yolov5s_1684x_int8_asym.bmodel

popd
