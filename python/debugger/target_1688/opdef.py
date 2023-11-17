# ==============================================================================
#
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================

"""
generated by old opdef_1688.py, used to retrival atomic op from `short_cmd, tsk_typ, tsk_eu_typ/sp_fun` fields
should be maintained manully.
"""
from typing import Dict, Tuple
from ..target_common import BaseTpuOp, cmd_base_reg, OpInfo, Tiu, Dma


# global data and type
# ------------------------------------------------------------
tiu_cls = dict()
dma_cls = dict()


class TiuCmdOp(BaseTpuOp, Tiu):
    opparam_converter = None  # assigned by BM1686Context instance

    opcode_bits = (41, 45)
    description = "TIU Operation."
    # extension
    eu_type = ()
    eu_bits = (45, 50)
    short_cmd = False  # long_code by default

    def __init__(self, cmd: cmd_base_reg) -> None:
        super().__init__(cmd)
        self.eu_name = tiu_cls[cmd.OP_NAME]["tsk_eu_typ"][cmd.tsk_eu_typ]

    def ops(self, *_):
        return 0

    @property
    def name(self):
        op_name = self.cmd.OP_NAME
        op_info = tiu_cls[self.cmd.OP_NAME]
        eu_type_id = self.cmd["tsk_eu_typ"]

        if len(op_info["tsk_eu_typ"]) != 0:
            # attribute_dic["tsk_typ"] = f'"{op_name}"'
            op_name = op_info["tsk_eu_typ"][eu_type_id]
        return op_name

    def __init_subclass__(cls) -> None:
        tiu_cls[cls.name] = {
            "description": cls.description,
            "tsk_eu_typ": cls.eu_type,
            "tsk_typ": cls.opcode,
            "short_cmd": cls.short_cmd,
        }
        return cls

    def __repr__(self) -> str:
        ci = self.cmd.core_id
        if self.operands == []:
            if self.attribute:
                attribute = f" {self.attribute}".replace(":", " =").replace("'", "")
                return (
                    # f"core_id: {self.core_id} " +
                    f'%B{self.cmd.cmd_id}C{ci} = "{self.name}"'
                    + f"(%D{self.cmd.cmd_id_dep}C{ci})"
                    + attribute
                )
            else:
                return self.description
        res_name, res_type_t = zip(*((x.name, x.type_str) for x in self.results))
        opd_name, opd_type_t = zip(*((x.name, x.type_str) for x in self.operands))

        attribute_dic = {}
        if self.attribute:
            attribute_dic.update(self.attribute)

        op_name = self.name
        attribute = f"{attribute_dic}" if len(attribute_dic) > 0 else ""
        attribute = f" {attribute}".replace(":", " =").replace("'", "")

        return (
            f"{', '.join(res_name)}, %B{self.cmd.cmd_id}C{ci} = \"{op_name}\""
            + f"({', '.join(opd_name)}, %D{self.cmd.cmd_id_dep}C{ci})"
            + attribute
            + f": ({', '.join(opd_type_t)}, none) -> ({', '.join(res_type_t)}, none)"
        )


class DmaCmdOp(BaseTpuOp, Dma):
    opparam_converter = None  # assigned by BM1686Context instance

    description = "GDMA Operation."
    opcode_bits = (32, 36)
    fun_bits = (36, 39)
    sp_fun = ()
    short_cmd = False  # long_code by default

    def __init_subclass__(cls) -> None:
        dma_cls[cls.name] = {
            "description": cls.description,
            "tsk_typ": cls.opcode,
            "sp_fun": cls.sp_fun,
            "short_cmd": cls.short_cmd,
        }
        return cls

    def __repr__(self):
        ci = self.cmd.core_id
        if self.operands == []:
            if self.attribute:
                attribute = f" {self.attribute}".replace(":", " =").replace("'", "")
                return (
                    f'%D{self.cmd.cmd_id}C{ci} = "{self.name}"'
                    + f"(%B{self.cmd.cmd_id_dep}C{ci})"
                    + attribute
                )
            else:
                return self.description
        opd_name, opd_type_t = zip(*((x.name, x.type_str) for x in self.operands))
        res_name, res_type_t = zip(*((x.name, x.type_str) for x in self.results))

        attribute_dic = {}
        if self.attribute:
            attribute_dic.update(self.attribute)

        op_name = self.name

        attribute = f"{attribute_dic}" if len(attribute_dic) > 0 else ""
        attribute = f" {attribute}".replace(":", " =").replace("'", "")

        return (
            f"{', '.join(res_name)}, %D{self.cmd.cmd_id}C{ci} = \"{op_name}\""
            + f"({', '.join(opd_name)}, %B{self.cmd.cmd_id_dep}C{ci})"
            + attribute
            + f": ({', '.join(opd_type_t)}, none) -> ({res_type_t[0]}, none)"
        )

    @property
    def name(self):
        op_name = self.cmd.OP_NAME
        op_info = dma_cls[self.cmd.OP_NAME]
        sp_func_id = self.cmd["cmd_special_function"]
        if len(op_info["sp_fun"]) != 0:
            # attribute_dic["tsk_typ"] = f'"{op_name}"'
            op_name = op_info["sp_fun"][sp_func_id]

        return op_name

    def ops(self, is_arch):
        return 0


class conv_op(TiuCmdOp):
    name = "CONV"
    opcode = 0
    eu_type = {0: "conv.normal"}
    description = "convolution"

    def ops(self, is_arch=False):
        return 0


class sconv_op(conv_op):
    name = "sCONV"
    short_cmd = True
    description = "short convolution"


class mm_op(TiuCmdOp):
    name = "MM"
    opcode = 2
    eu_type = {1: "mm.normal"}
    description = "matrix multiply"

    def ops(self, is_arch=False):
        return 0


class smm_op(mm_op):
    name = "sMM"
    short_cmd = True
    description = "short matrix multiply"


class mm2_op(TiuCmdOp):
    name = "MM2"
    opcode = 2
    eu_type = {4: "mm2.nn", 5: "mm2.nt", 6: "mm2.tt"}
    description = "matrix multiply2"

    def ops(self, is_arch=False):
        return 0


class smm2_op(mm2_op):
    name = "sMM2"
    short_cmd = True
    description = "short matrix multiply2"


class cmp_op(TiuCmdOp):
    name = "CMP"
    opcode = 13
    eu_type = {
        22: "cmp.gt_and_sel_gt",
        23: "cmp.sel_gt",
        24: "cmp.sel_eq",
        25: "cmp.lt_and_sel_lt",
        26: "cmp.sel_lt",
    }
    description = "fused_cmpare"

    def ops(self, is_arch=False):
        return 0


class scmp_op(cmp_op):
    name = "sCMP"
    short_cmd = True
    description = "short fused_cmpare"


class sfu_op(TiuCmdOp):
    name = "SFU"
    opcode = 9
    eu_type = {
        12: "sfu.taylor_4x",
        13: "sfu.taylor",
        15: "sfu.normalize",
        17: "sfu.rsqrt",
    }
    description = "special_function"

    def ops(self, is_arch=False):
        return 0


class ssfu_op(sfu_op):
    name = "sSFU"
    short_cmd = True
    description = "short special_function"


class lin_op(TiuCmdOp):
    name = "LIN"
    opcode = 10
    eu_type = {1: "lin.mac", 20: "lin.square_sum", 21: "lin.square_diff"}
    description = "fused_linear"

    def ops(self, is_arch):
        return 0


class slin_op(lin_op):
    name = "sLIN"
    short_cmd = True
    description = "short fused_linear"


class vc_op(TiuCmdOp):
    name = "VC"
    opcode = 14
    eu_type = {
        0: "vc.mul",
        2: "vc.add",
        3: "vc.sub",
        4: "vc.max",
        5: "vc.min",
        7: "vc.and",
        8: "vc.or",
        9: "vc.xor",
        10: "vc.select_gt",
        11: "vc.select_eq",
        12: "vc.div",
        13: "vc.select_lt",
        15: "vc.add_satu",
        16: "vc.sub_satu",
        20: "vc.mul_satu",
        23: "vc.mulDHR",
    }
    description = "vector correlation"

    def ops(self, is_arch):
        return 0


class svc_op(vc_op):
    name = "sVC"
    short_cmd = True
    description = "short vector correlation"


class ar_op(TiuCmdOp):
    name = "AR"
    opcode = 3
    eu_type = {
        0: "arith.mul",
        1: "arith.not",
        2: "arith.add",
        3: "arith.sub",
        4: "arith.max",
        5: "arith.min",
        6: "arith.logic_shift",
        7: "arith.and",
        8: "arith.or",
        9: "arith.xor",
        10: "arith.select_great",
        11: "arith.select_equal",
        12: "arith.div",
        13: "arith.select_less",
        14: "arith.cast",
        15: "arith.add_satu",
        16: "arith.sub_satu",
        18: "arith.mac",
        19: "arith.copy",
        20: "arith.mul_satu",
        21: "arith.arith_shift",
        22: "arith.rotate_shift",
        26: "arith.abs",
        27: "arith.fsub_abs",
        29: "arith.get_first_one",
        30: "arith.get_first_zero",
    }
    description = "arithmetic"

    def ops(self, is_arch):
        return 0


class sar_op(ar_op):
    name = "sAR"
    short_cmd = True
    description = "short arithmetic"


class pord_op(TiuCmdOp):
    name = "PorD"
    opcode = 1
    eu_type = {
        0: "pord.depthwise",
        1: "pord.avgpooling",
        3: "pord.minpooling",
        4: "pord.maxpooling",
        5: "pord.roi_depthwise",
        6: "pord.roi_avgpooling",
        7: "pord.roi_maxpooling",
        8: "pord.roi_minpooling",
    }
    description = "depthwise or pooling"

    def ops(self, is_arch):
        return 0


class spord_op(pord_op):
    name = "sPorD"
    short_cmd = True
    description = "short depthwise or pooling"


class rqdq_op(TiuCmdOp):
    name = "RQ&DQ"
    opcode = 4
    eu_type = {
        0: "quant.rq0",
        1: "quant.rq1",
        3: "quant.dq0",
        4: "quant.dq1",
    }
    description = "RQ && DQ"

    def _set_op(self, reg):
        return ([],) * 3

    def ops(self, is_arch):
        return 0


class srqdq_op(rqdq_op):
    name = "sRQ&sDQ"
    short_cmd = True
    description = "short RQ && DQ"


class sg_op(TiuCmdOp):
    name = "SG"
    opcode = 6
    eu_type = {
        0: "sg.pl_gather_d1coor",
        1: "sg.pl_gather_d2coor",
        2: "sg.pl_gather_rec",
        3: "sg.pl_scatter_d1coor",
        4: "sg.pl_scatter_d2coor",
        5: "sg.pe_s_gather_d1coor",
        6: "sg.pe_s_scatter_d1coor",
        8: "sg.pe_s_mask_select",
        9: "sg.pe_s_nonzero",
        13: "sg.pe_s_gather_hzd",
        14: "sg.pe_s_scatter_hzd",
        15: "sg.pe_s_mask_selhzd",
        16: "sg.pe_s_nonzero_hzd",
    }
    description = "scatter_gather"

    def ops(self, is_arch):
        return 0


class ssg_op(sg_op):
    name = "sSG"
    short_cmd = True
    description = "short scatter_gather"


class sgl_op(TiuCmdOp):
    name = "SGL"
    opcode = 6
    eu_type = {17: "sgl.pe_s_gather_line", 18: "sgl.pe_s_scatter_line"}
    description = "scatter_gather_line"

    def ops(self, is_arch):
        return 0


class ssgl_op(sgl_op):
    name = "sSGL"
    short_cmd = True
    description = "short scatter_gather_line"


class transbc_op(TiuCmdOp):
    name = "CW&BC"
    opcode = 5
    eu_type = {
        0: "tsbc.cw_ts",
        1: "tsbc.wc_ts",
        2: "tsbc.l_copy",
        3: "tsbc.l_bc",
        4: "tsbc.s_bc",
        5: "tsbc.s_distribute",
    }
    description = "TRANS && BC"

    def ops(self, is_arch):
        return 0


class stransbc_op(transbc_op):
    name = "sCW&sBC"
    short_cmd = True
    description = "short TRANS && BC"


class tiu_sys_tr_acc(TiuCmdOp):
    name = "SYS_TR_ACC"
    opcode = 12
    short_cmd = None
    eu_bits = (45, 48)
    eu_type = {
        0: "system_tr_wr.wr_imm",
    }
    description = "system tr wr"

    def ops(self, is_arch):
        return 1


class tiu_sys(TiuCmdOp):
    name = "SYS"
    opcode = 15
    short_cmd = None
    eu_type = {
        1: "system.spb",
        2: "system.swr",
        3: "system.swr_from_lmm",
        4: "system.swr_collect_from_lmm",
        8: "system.send_msg",
        9: "system.wait_msg",
        30: "system.nop",
        31: "system.end",
    }
    description = "system"

    def ops(self, is_arch):
        return 1

    def _set_op(self, reg):
        return ([],) * 3


class dma_tensor(DmaCmdOp):
    name = "DMA_tensor（0x000）"
    opcode = 0
    sp_fun = {
        0: "dma.tensor",
        1: "dma.tensor.transpose",
        2: "dma.tensor.collect",
        3: "dma.tensor.broadcast",
        4: "dma.tensor.distribute",
        5: "dma.tensor.4bank_copy",
        6: "dma.tensor.4bank_broadcast",
    }
    description = "DMA tensor"


class dma_matrix(DmaCmdOp):
    name = "DMA_matrix"
    opcode = 1
    sp_fun = {
        0: "dma.matrix",
        1: "dma.matrix.transpose",
    }
    description = "DMA matrix"


class dma_masked_select(DmaCmdOp):
    name = "DMA_masked_select"
    opcode = 2
    sp_fun = {
        0: "dma.masked_select",
        1: "dma.masked_select.ncw",
    }
    description = "DMA masked select"


class dma_general(DmaCmdOp):
    name = "DMA_general"
    opcode = 3
    sp_fun = {
        0: "dma.general",
        1: "dma.general.broadcast",
    }
    description = "DMA general"


class dma_cw_transpose(DmaCmdOp):
    name = "DMA_cw_transpose"
    opcode = 4
    sp_fun = {0: "dma.cw_transpose"}
    description = "DMA CW Transpose"


class dma_nonzero(DmaCmdOp):
    name = "DMA_nonzero"
    opcode = 5
    sp_fun = {0: "dma.nonzero"}
    description = "DMA nonzero"


class dma_sys(DmaCmdOp):
    name = "sDMA_sys"
    opcode = 6
    short_cmd = True
    sp_fun = {
        0: "dma.sys.chain_end",
        1: "dma.sys.nop",
        2: "dma.sys.sys_tr_wr",
        3: "dma.sys.sys_send",
        4: "dma.sys.sys_wait",
    }
    description = "short DMA sys"


class dma_gather(DmaCmdOp):
    name = "DMA_gather"
    opcode = 7
    sp_fun = {0: "gdma.gather"}
    description = "DMA gather"


class dma_scatter(DmaCmdOp):
    name = "DMA_scatter"
    opcode = 8
    sp_fun = {0: "gdma.scatter"}
    description = "DMA scatter"


class dma_reverse(DmaCmdOp):
    name = "DMA_reverse"
    opcode = 9
    sp_fun = {
        0: "dma.reverse.w",
        1: "dma.reverse.h",
        2: "dma.reverse.c",
        3: "dma.reverse.n",
    }
    description = "DMA reverse"


class dma_compress(DmaCmdOp):
    name = "DMA_compress"
    opcode = 10
    sp_fun = {
        0: "dma.compress.non_random_access",
        1: "dma.compress.random_access",
    }
    description = "DMA compress"


class dma_decompress(DmaCmdOp):
    name = "DMA_decompress "
    opcode = 11
    sp_fun = {
        0: "dma.decompress.non_random_access",
        1: "dma.decompress.random_access",
    }
    description = "DMA decompress"


# build tiu and dma search tree
# search by cmd_short, tsk_typ, tsk_eu_type
tiu_index: Dict[Tuple[int, int, int], OpInfo] = {}

for k, v in tiu_cls.items():
    if len(v["tsk_eu_typ"]) == 0:
        tsk_eu_typ = {0: "none"}
    else:
        tsk_eu_typ = v["tsk_eu_typ"]

    if isinstance(tsk_eu_typ, range):
        tsk_eu_typ = {i: f"ana_{i}" for i in tsk_eu_typ}

    for eu_type, eu_name in tsk_eu_typ.items():
        if v["short_cmd"] is None:
            v["short_cmd"] = 0
        tiu_index[(int(v["short_cmd"]), v["tsk_typ"], eu_type)] = OpInfo(k, eu_name)


# search by cmd_short, tsk_typ, sp_fun(special function)
dma_index: Dict[Tuple[int, int, int], OpInfo] = {}
for k, v in dma_cls.items():
    if len(v["sp_fun"]) == 0:
        sp_fun = {0: "none"}
    else:
        sp_fun = v["sp_fun"]

    for sp_typ, sp_name in sp_fun.items():
        dma_index[(int(v["short_cmd"]), v["tsk_typ"], sp_typ)] = OpInfo(k, sp_name)
