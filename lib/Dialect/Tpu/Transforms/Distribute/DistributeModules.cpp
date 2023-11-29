//===----------------------------------------------------------------------===//
//
// Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
//
// TPU-MLIR is licensed under the 2-Clause BSD License except for the
// third-party components.
//
//===----------------------------------------------------------------------===//
#include "tpu_mlir/Dialect/Tpu/Transforms/Distribute/Distribute.h"

namespace tpu_mlir {
namespace tpu {

class SubFunction {
public:
  SubFunction(int64_t devid, int64_t step) : devid(devid), step(step) {
    need_none = false;
  }
  int64_t devid;
  int64_t step;
  bool need_none;
  std::vector<Operation *> ops;
};

static constexpr llvm::StringRef DEVICE_ID = "device_id";
static constexpr llvm::StringRef STEP = "step";

struct OpReorderPattern : public RewritePattern {
  OpReorderPattern(MLIRContext *context)
      : RewritePattern(MatchAnyOpTypeTag(), 1, context) {}
  LogicalResult matchAndRewrite(Operation *op,
                                PatternRewriter &rewriter) const override {
    if (isa<FuncOp, top::WeightOp, top::NoneOp>(op)) {
      return failure();
    }
    llvm::SmallVector<Operation *, 8> opds;
    llvm::SmallVector<Operation *, 8> weights;
    for (auto opd : op->getOperands()) {
      auto op_ = opd.getDefiningOp();
      if (op_ == nullptr || isa<top::NoneOp, FuncOp>(op_)) {
        continue;
      }
      if (isa<top::WeightOp>(op_)) {
        weights.push_back(op_);
      } else {
        opds.push_back(op_);
      }
    }
    opds.append(weights);
    bool fixed = false;
    auto last_op = op;
    auto num_opds = opds.size();
    if (num_opds != 0) {
      for (auto it = opds.rbegin(); it != opds.rend(); ++it) {
        if ((*it)->getNextNode() != last_op) {
          (*it)->moveBefore(last_op);
          fixed = true;
        }
        last_op = *it;
      }
    }
    return fixed ? success() : failure();
  }
};

static void getInputsOutputs(std::vector<Operation *> &ops,
                             std::vector<Value> &inputs,
                             std::vector<Value> &outputs) {
  std::vector<Value> allValues;
  for (auto op : ops) {
    for (auto v : op->getResults()) {
      allValues.push_back(v);
    }
  }
  for (auto op : ops) {
    for (auto v : op->getOperands()) {
      if (find(inputs.begin(), inputs.end(), v) != inputs.end()) {
        continue;
      }
      auto inOp = v.getDefiningOp();
      if (inOp == nullptr || isa<top::NoneOp>(inOp)) {
        continue;
      }
      if (find(allValues.begin(), allValues.end(), v) == allValues.end()) {
        inputs.push_back(v);
      }
    }
    for (auto v : op->getResults()) {
      if (find(outputs.begin(), outputs.end(), v) != outputs.end()) {
        continue;
      }
      // if (std::distance(v.user_begin(), v.user_end()) == 0) {
      //   outputs.push_back(v);
      // }
      for (auto use : v.getUsers()) {
        if (find(ops.begin(), ops.end(), use) == ops.end()) {
          outputs.push_back(v);
          break;
        }
      }
    }
  }
}

static void buildSubFunction(std::shared_ptr<SubFunction> sf, ModuleOp m) {
  if (sf == nullptr || sf->ops.empty()) {
    return;
  }
  auto ctx = m.getContext();
  std::vector<Value> fnInputs;
  std::vector<Value> fnOutputs;
  getInputsOutputs(sf->ops, fnInputs, fnOutputs);
  std::vector<Type> argType;
  std::vector<Type> resType;
  std::vector<Location> argLoc;
  std::vector<Location> retLoc;
  for (auto input : fnInputs) {
    argType.push_back(input.getType());
    argLoc.push_back(module::getLoc(input));
  }
  for (auto output : fnOutputs) {
    resType.push_back(output.getType());
    retLoc.push_back(module::getLoc(output));
  }
  auto name = module::getName(m).str();
  std::string func_name =
      name + "_" + std::to_string(sf->step) + "_" + std::to_string(sf->devid);
  OpBuilder builder(m.getContext());
  std::vector<NamedAttribute> attrs;
  attrs.push_back(
      builder.getNamedAttr(STEP, builder.getI64IntegerAttr(sf->step)));
  attrs.push_back(
      builder.getNamedAttr(DEVICE_ID, builder.getI64IntegerAttr(sf->devid)));
  auto fnType = builder.getFunctionType(llvm::ArrayRef<Type>{argType},
                                        llvm::ArrayRef<Type>{resType});
  auto fnOp =
      FuncOp::create(NameLoc::get(builder.getStringAttr(func_name)), func_name,
                     fnType, ArrayRef<NamedAttribute>(attrs));
  auto block = fnOp.addEntryBlock();
  builder.setInsertionPointAfterValue(fnOutputs.back());
  Location call_loc = retLoc[0];
  if (retLoc.size() > 1) {
    call_loc = FusedLoc::get(ctx, retLoc);
  }
  func::CallOp callOp =
      builder.create<func::CallOp>(call_loc, func_name, resType, fnInputs);
  for (auto it : llvm::enumerate(callOp.getResults())) {
    fnOutputs[it.index()].replaceUsesWithIf(
        it.value(), [&](OpOperand &operand) {
          Operation *user = operand.getOwner();
          return find(sf->ops.begin(), sf->ops.end(), user) == sf->ops.end();
        });
  }
  builder.setInsertionPointToStart(block);
  top::NoneOp noneOp;
  if (sf->need_none) {
    noneOp = builder.create<top::NoneOp>(m.getLoc(), builder.getNoneType());
  }
  auto retOp = builder.create<func::ReturnOp>(call_loc, fnOutputs);
  for (auto op : sf->ops) {
    if (isa<top::NoneOp>(op)) {
      continue;
    }
    for (auto it : llvm::enumerate(op->getOperands())) {
      if (isa_and_nonnull<top::NoneOp>(it.value().getDefiningOp())) {
        op->setOperand(it.index(), noneOp);
      }
    }
    op->moveBefore(retOp);
  }
  m.push_back(fnOp);
  if (sf->need_none) {
    builder.setInsertionPointAfter(noneOp);
  } else {
    builder.setInsertionPointToStart(block);
  }
  for (auto it : llvm::enumerate(fnInputs)) {
    auto v = it.value();
    auto idx = it.index();
    auto arg = block->getArgument(idx);
    arg.setLoc(argLoc[idx]);
    auto input =
        builder.create<top::InputOp>(argLoc[idx], v.getType(), ValueRange{arg});
    v.replaceUsesWithIf(input, [&](OpOperand &operand) {
      Operation *user = operand.getOwner();
      return find(sf->ops.begin(), sf->ops.end(), user) != sf->ops.end();
    });
  }
}

static void insert_subop(std::shared_ptr<SubFunction> &subf, Operation *op) {
  for (auto opd : op->getOperands()) {
    auto op_ = opd.getDefiningOp();
    if (isa<top::WeightOp>(op_)) {
      subf->ops.push_back(op_);
    } else if (isa<top::NoneOp>(op_) && subf->need_none == false) {
      subf->need_none = true;
    }
  }
  subf->ops.push_back(op);
}

// MatMulSliceMerge use backward
static void collect_ops_backward(std::shared_ptr<SubFunction> &subf,
                                 Operation *op, int cur_device) {
  if (std::find(subf->ops.begin(), subf->ops.end(), op) != subf->ops.end()) {
    return;
  }
  std::vector<Value> operands(op->operand_begin(), op->operand_end());
  bool skip = false;
  for (auto [idx, opd] : llvm::enumerate(operands)) {
    auto op_ = opd.getDefiningOp();
    if (auto begin = dyn_cast_or_null<tpu::DistributionBeginOp>(op_)) {
      std::vector<Value> results(op_->result_begin(), op_->result_end());
      int i = std::find(results.begin(), results.end(), opd) - results.begin();
      auto begin_methods = module::getI64Array(begin.getBeginMethods());
      auto pre_op = op_->getOperand(i).getDefiningOp();
      if (isa<tpu::IdentityOp>(pre_op)) {
        op->setOperand(idx, pre_op->getOperand(cur_device));
      } else {
        op->setOperand(idx, op_->getOperand(i));
      }
      skip = (isa<tpu::SliceOp>(op) &&
              begin_methods->at(i) ==
                  (int)DistributionBeginMethod::BeginFromSplit);
      continue;
    } else if (!isa<top::WeightOp, top::NoneOp, top::InputOp>(op_)) {
      collect_ops_backward(subf, op_, cur_device);
    } else if (isa<top::WeightOp>(op_)) {
      subf->ops.push_back(op_);
    } else if (isa<top::NoneOp>(op_) && subf->need_none == false) {
      subf->need_none = true;
    }
  }
  if (!skip) {
    subf->ops.push_back(op);
  }
}

// MatMulTopK use forward
static void collect_ops_forward(std::shared_ptr<SubFunction> &subf,
                                Operation *op) {
  for (auto it : llvm::enumerate(op->getOperands())) {
    auto op_ = it.value().getDefiningOp();
    if (isa_and_nonnull<tpu::DistributionBeginOp>(op_)) {
      std::vector<Value> results(op_->result_begin(), op_->result_end());
      int idx = std::find(results.begin(), results.end(), it.value()) -
                results.begin();
      op->setOperand(it.index(), op_->getOperand(idx));
    }
  }
  insert_subop(subf, op);
  for (auto u : op->getUsers()) {
    if (isa<tpu::DistributionEndOp>(u)) {
      continue;
    }
    collect_ops_forward(subf, u);
  }
}

static void buildDistibution(tpu::DistributionBeginOp begin,
                             tpu::DistributionEndOp end, ModuleOp m,
                             int64_t num_devices, int64_t step) {
  std::vector<Operation *> begins(begin->user_begin(), begin->user_end());
  std::vector<Value> ends(end->operand_begin(), end->operand_end());
  for (int i = 0; i < num_devices; i++) {
    auto subf = std::make_shared<SubFunction>(i, step);
    if (begins.size() == num_devices) {
      collect_ops_forward(subf, begins[i]);
    } else if (ends.size() == num_devices) {
      collect_ops_backward(subf, ends[i].getDefiningOp(), i);
    } else {
      assert(ends.size() % num_devices == 0);
      int num_output = ends.size() / num_devices;
      for (int j = 0; j < num_output; ++j) {
        collect_ops_backward(subf, ends[i * num_output + j].getDefiningOp(), i);
      }
    }
    buildSubFunction(subf, m);
  }
}

static int64_t buildEndToSum(tpu::DistributionEndOp end, ModuleOp m,
                             std::vector<Value> &origin_operands,
                             int64_t num_devices, int64_t step,
                             int cur_out_idx) {
  OpBuilder builder(end.getContext());
  builder.setInsertionPointAfter(end);
  int times = num_devices > 2 ? std::ceil(std::sqrt(num_devices)) : 1;
  std::vector<std::shared_ptr<tpu_mlir::tpu::SubFunction>> subf_v;
  std::vector<Value> operands = origin_operands;
  std::vector<Value> new_operands;
  assert(operands.size() % 2 == 0);
  for (int t = 0; t < times; ++t) {
    for (int i = 0; i < operands.size(); ++i) {
      // if (i + 1 == operands.size() && operands.size() % 2 == 1) {
      //   new_operands.push_back(operands[i]);
      //   continue;
      // }
      // the other operand idx
      int k = 1 << t;
      int j = (i / k) % 2 == 0 ? i + k : i - k;

      std::string suffix = std::string("add_") + std::to_string(cur_out_idx) +
                           "_" + std::to_string(t) + "_" + std::to_string(i);
      auto loc = module::getLocLike(origin_operands[i], suffix);
      auto add = builder.create<tpu::AddOp>(
          loc, operands[i].getType(),
          mlir::ValueRange{operands[i], operands[j]});
      new_operands.push_back(add.getOutput());
      auto subf = std::make_shared<SubFunction>(i, step);
      insert_subop(subf, add);
      // if (t == times - 1 && i == 0) {
      //   module::setLoc(add.getOutput(),
      //                  module::getLoc(end.getOutputs()[cur_out_idx]));
      //   end.getOutputs()[cur_out_idx].replaceAllUsesWith(add.getOutput());
      // }
      subf_v.emplace_back(std::move(subf));
    }
    step++;
    operands = new_operands;
    new_operands.clear();
  }

  builder.setInsertionPointAfterValue(end.getOutputs()[cur_out_idx]);
  auto new_loc = module::getLoc(end.getOutputs()[cur_out_idx]);
  auto new_type = end.getOutputs()[cur_out_idx].getType();
  auto all_reduce_op =
      builder.create<tpu::IdentityOp>(new_loc, new_type, operands);
  end.getOutputs()[cur_out_idx].replaceAllUsesWith(
      all_reduce_op.getOutput()[0]);

  builder.setInsertionPoint(all_reduce_op);
  for (auto f : subf_v) {
    buildSubFunction(f, m);
  }
  return step;
}

static int64_t buildEndToTopK(tpu::DistributionEndOp end, ModuleOp m,
                              std::vector<Value> operands, int64_t num_devices,
                              int64_t step, int cur_out_idx) {
  OpBuilder builder(end.getContext());
  builder.setInsertionPointAfter(end);
  int times = num_devices > 2 ? std::ceil(std::sqrt(num_devices)) : 1;
  std::vector<std::shared_ptr<tpu_mlir::tpu::SubFunction>> subf_v;
  std::vector<Value> new_operands;
  for (int t = 0; t < times; t++) {
    for (int i = 0; i < operands.size(); i += 4) {
      if (i + 2 == operands.size()) {
        new_operands.push_back(operands[i]);
        new_operands.push_back(operands[i + 1]);
        continue;
      }
      auto subf = std::make_shared<SubFunction>(
          (i / 2 * (int)std::pow(2, t)) % num_devices, step);
      auto value = operands[i];
      auto indice = operands[i + 1];
      auto value2 = operands[i + 2];
      auto indice2 = operands[i + 3];
      auto suffix =
          "cmp_" + std::to_string(cur_out_idx) + "_" + std::to_string(i);
      auto loc = module::getLocLike(operands[i + 1], suffix);
      std::vector<NamedAttribute> attrs;
      attrs.push_back(builder.getNamedAttr(
          "mode", builder.getStringAttr("GreaterOrEqual")));
      auto cmp = builder.create<tpu::CompareOp>(
          loc, value.getType(), ValueRange{value, value2}, attrs);
      insert_subop(subf, cmp);

      suffix =
          "indice_" + std::to_string(cur_out_idx) + "_" + std::to_string(i);
      loc = module::getLocLike(operands[i + 1], suffix);
      auto indice_select = builder.create<tpu::WhereOp>(
          loc, indice.getType(), ValueRange{cmp.getOutput(), indice, indice2});
      indice = indice_select.getOutput();
      insert_subop(subf, indice_select);

      if (t == times - 1) {
        module::setLoc(indice, module::getLoc(end.getOutputs()[0]));
        end.getOutputs()[0].replaceAllUsesWith(indice);
        end.erase();
        for (auto f : subf_v) {
          buildSubFunction(f, m);
        }
        if (subf->ops.size() > 0) {
          buildSubFunction(subf, m);
        }
        return step; // std::move(subf);
      }

      suffix = "value_" + std::to_string(cur_out_idx) + "_" + std::to_string(i);
      loc = module::getLocLike(operands[i], suffix);
      auto value_select = builder.create<tpu::WhereOp>(
          loc, value.getType(), ValueRange{cmp.getOutput(), value, value2});
      value = value_select.getOutput();
      insert_subop(subf, value_select);

      subf_v.emplace_back(std::move(subf));
      new_operands.push_back(value);
      new_operands.push_back(indice);
    }
    step++;
    operands = new_operands;
    new_operands.clear();
  }

  // for (auto f : subf_v) {
  //   buildSubFunction(f, m);
  // }
  return step;
}

static int64_t buildEndToConcat(tpu::DistributionEndOp end, ModuleOp m,
                                std::vector<Value> operands,
                                int64_t num_devices, int64_t step,
                                int cur_out_idx) {
  // pass, let it hold in its device
  return step;
}

static std::shared_ptr<SubFunction> buildEndOp(tpu::DistributionEndOp end,
                                               ModuleOp m, int64_t num_devices,
                                               int64_t &step) {
  std::vector<Value> operands(end.operand_begin(), end.operand_end());
  int num_outputs = operands.size() / num_devices;
  std::vector<Value> new_operands;

  // std::vector<std::shared_ptr<tpu_mlir::tpu::SubFunction>> subf_v;

  int cur_step;
  int max_step = step;
  auto end_methods = getEndMethodArray(end);
  for (size_t i = 0; i < num_outputs; ++i) {
    auto mode = static_cast<DistributionEndMethod>(end_methods->at(i));

    new_operands.clear();
    switch (mode) {
    case DistributionEndMethod::EndToSum: {
      for (size_t j = 0; j < num_devices; ++j) {
        new_operands.push_back(operands[j * num_outputs + i]);
      }
      cur_step = buildEndToSum(end, m, new_operands, num_devices, step, i);
      max_step = std::max(cur_step, max_step);
      break;
    }
    case DistributionEndMethod::EndToTopK: {
      for (size_t j = 0; j < num_devices; ++j) {
        new_operands.push_back(operands[j * num_outputs + i]);
        new_operands.push_back(operands[j * num_outputs + i + 1]);
      }
      cur_step = buildEndToTopK(end, m, new_operands, num_devices, step, i);
      max_step = std::max(cur_step, max_step);
      i++;
      break;
    }
    case DistributionEndMethod::EndToConcat: {
      cur_step = buildEndToConcat(end, m, new_operands, num_devices, step, i);
      max_step = std::max(cur_step, max_step);
      break;
    }
    default: {
      llvm_unreachable("Not Implemented");
      break;
    }
    }
  }
  step = max_step;
  // TODO: erase the EndOp and connect the Input/Output
  return nullptr;
}

static int64_t getDeviceId(FuncOp func) {
  return func->getAttrOfType<IntegerAttr>(DEVICE_ID).getInt();
}

static int64_t getStep(FuncOp func) {
  return func->getAttrOfType<IntegerAttr>(STEP).getInt();
}

class Function2Module : public OpRewritePattern<func::CallOp> {
public:
  using OpRewritePattern::OpRewritePattern;
  LogicalResult matchAndRewrite(func::CallOp op,
                                PatternRewriter &rewriter) const override {
    auto m = module::getModuleOp();
    auto func = module::getFuncOp(m, op.getCallee());
    auto device_id = getDeviceId(func);
    auto step = getStep(func);
    rewriter.setInsertionPointToStart(m.getBody());
    auto sub_m = rewriter.create<ModuleOp>(func.getLoc(), op.getCallee());
    module::setSubModuleId(sub_m, device_id, step);
    func->removeAttr(DEVICE_ID);
    func->removeAttr(STEP);
    func->moveBefore(sub_m.getBody(), sub_m.getBody()->begin());
    func.setName("main");
    return success();
  }
};

static void distributeToOneModule(ModuleOp m) {
  auto func = module::getFuncOp(m, "main");
  OpBuilder builder(m.getContext());
  builder.setInsertionPointToStart(m.getBody());
  auto sub_m = builder.create<ModuleOp>(m.getLoc(), module::getName(m));
  module::setSubModuleId(sub_m, 0, 0);
  func->moveBefore(sub_m.getBody(), sub_m.getBody()->begin());
}

void distributeModules(ModuleOp m, int64_t num_device) {
  auto main = module::getMainFuncOp(m);
  std::vector<StringRef> input_names;
  std::vector<StringRef> output_names;
  for (auto in : main.getOps<top::InputOp>()) {
    input_names.push_back(module::getName(in.getOutput()));
  }
  for (auto ret : main.getOps<func::ReturnOp>()) {
    for (auto v : ret.getOperands()) {
      output_names.push_back(module::getName(v));
    }
  }
  module::setInputs(input_names);
  module::setOutputs(output_names);
  if (num_device == 1) {
    distributeToOneModule(m);
    return;
  }

  auto ctx = m.getContext();
  for (auto func : m.getOps<FuncOp>()) {
    RewritePatternSet patterns(ctx);
    patterns.add<OpReorderPattern>(ctx);
    applyPatternsAndFoldGreedily(func, std::move(patterns));
  }

  std::shared_ptr<SubFunction> subf = nullptr;
  bool in_distribution = false;
  int64_t step = 0;
  tpu::DistributionBeginOp begin;
  // split to different functions
  main.walk([&](Operation *op) {
    if (isa<top::InputOp, top::WeightOp, FuncOp, top::NoneOp, func::ReturnOp,
            func::CallOp>(op)) {
      // do nothing
    } else {
      if (isa<tpu::DistributionBeginOp>(op)) {
        // for some patterns maybe do slice here
        buildSubFunction(subf, m);
        in_distribution = true;
        begin = cast<tpu::DistributionBeginOp>(op);
      } else if (isa<tpu::DistributionEndOp>(op)) {
        auto end = cast<tpu::DistributionEndOp>(op);
        buildDistibution(begin, end, m, num_device, step++);
        in_distribution = false;
        subf = buildEndOp(end, m, num_device, step);
        // subf = nullptr;
      } else if (in_distribution) {
        // do nothing
      } else if (subf == nullptr) {
        subf = std::make_shared<SubFunction>(0, step++);
        insert_subop(subf, op);
      } else {
        insert_subop(subf, op);
      }
    }
  });
  if (subf != nullptr) {
    buildSubFunction(subf, m);
    subf = nullptr;
  }

  // each function create one module
  applyPatternOnce<Function2Module>(m);
  // remove main, and functions
  auto ops = m.getOps<FuncOp>();
  std::vector<FuncOp> funcs(ops.begin(), ops.end());
  for (auto f : funcs) {
    f.erase();
  }
  // make moudle order to be step by step and device by device
  auto subs = m.getOps<ModuleOp>();
  std::vector<ModuleOp> modules(subs.begin(), subs.end());
  if (modules.size() <= 1) {
    return;
  }

  for (auto s : modules) {
    for (auto func : s.getOps<FuncOp>()) {
      RewritePatternSet patterns(ctx);
      patterns.add<OpReorderPattern>(ctx);
      applyPatternsAndFoldGreedily(func, std::move(patterns));
    }
  }

  std::sort(modules.begin(), modules.end(), [](ModuleOp a, ModuleOp b) {
    int64_t a_devid, a_step, b_devid, b_step;
    module::getSubModuleId(a, a_devid, a_step);
    module::getSubModuleId(b, b_devid, b_step);
    return a_step < b_step || (a_step == b_step && a_devid < b_devid);
  });
  for (int i = 1; i < modules.size(); i++) {
    modules[i]->moveAfter(modules[i - 1]);
  }
}

} // namespace tpu
} // namespace tpu_mlir
