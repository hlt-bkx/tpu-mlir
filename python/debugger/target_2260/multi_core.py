# ==============================================================================
#
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================

"""
This essentially simulates the engine synchronization mechanism of cmodel/hardware

Think of the instruction list for each core as a state machine.
The principle of consumption instructions:
if it is a normal instruction direct consumption, if it is a sys instruction,
it will be consumed according to the rules
1. The send commands no matter tiu or dma will be represented as Status.PRODUCING.
2. The wait command requires send_cnt to meet the requirements before it can be consumed
The cmds taken as in args are always from one core, meanwhile there should be many cores.
And the cmds in one core are always sorted: <send cmds> come first -> then <wait cmds> -> then the <OP cmds>, and repeat if possible.
Two engine(must be 2), tiu and dma are used in each core when synchronizing.

The sender sends a message to the message queue,
and the message queue adds 1 to the sent_cnt field
where the ID is located after receiving the message,
and sets the remain_wait_cnt field to wait_cnt = 2 for each core;
the receiver polls whether the sent_cnt at the
corresponding position in the message queue has
met the requirements, if it is satisfied,
decrease reamin_wait_cnt by one.
When it is reduced to 0, this position is cleared to 0,
and the process of message synchronization is completed so far.

The final wait cmd where reamin_wait_cnt was reduced to 0, will have a status as Status.CONSUMED
The other wait cmd except the last one will have a status as Status.RECIEVING
"""

from enum import Enum
import textwrap
from .regdef import sDMA_sys_reg as dma_sys, SYS_reg as tiu_sys
from .opparam import SYS_converter, sDMA_sys_converter
from .context import SG2260Context
from ..atomic_dialect import INDENT_SPACE, Node


class CMD_TYPE(Enum):
    SYNC = 0
    OP = 1


class SYS_TYPE(Enum):
    SEND = 0
    WAIT = 1


class Status(Enum):
    # for msg use
    PRODUCING = 0
    WAITING = 1  # normally won't appear
    RECIEVING = 2
    CONSUMED = 3
    # for op use
    OP = 4


class Msg:
    def __init__(self):
        self.sent_cnt = 0
        self.remain_wait_cnt = 0


class MsgCore(Node):
    def __init__(self, msgcore_id, core_nums, mlir_cmds, mlir_rets, indent=0):
        self.msgcore_id = msgcore_id
        self.core_id = mlir_cmds[0].cmd.core_id
        self.core_nums = core_nums
        self.mlir_cmds = mlir_cmds
        self.mlir_rets = mlir_rets
        self.indent = indent

        self.in_msg_id = mlir_cmds[0].attribute["msg_id"]
        self.out_msg_id = mlir_cmds[-1].attribute.get("msg_id", None)
        self.in_msg = mlir_cmds[0].cmd
        self.out_msg = mlir_cmds[-1].cmd
        self.msg_operand = []
        self.msg_result = []

        # get in_msg and out_msg
        self.get_DAG()

    def get_DAG(self):
        assert isinstance(self.in_msg, (tiu_sys, dma_sys))
        if isinstance(self.in_msg, tiu_sys):
            self.msg_operand = f"%D{self.in_msg.cmd_id_dep}C{self.in_msg.core_id}"
        elif isinstance(self.in_msg, dma_sys):
            self.msg_operand = f"%B{self.in_msg.cmd_id_dep}C{self.in_msg.core_id}"

        if isinstance(self.out_msg, (tiu_sys, dma_sys)):
            if isinstance(self.out_msg, tiu_sys):
                self.msg_result = f"%B{self.out_msg.cmd_id}C{self.out_msg.core_id}"
            elif isinstance(self.out_msg, dma_sys):
                self.msg_result = f"%D{self.out_msg.cmd_id}C{self.out_msg.core_id}"

    def __str__(self):
        repr_head = f'{self.msg_result}, %msg{self.out_msg_id} = "@core_{self.core_id}"({self.msg_operand}, %msg{self.in_msg_id}) {{'
        repr_tail = "}"

        ops_str_list = []
        for idx, x in enumerate(self.mlir_cmds):
            if x.operands == []:
                str_x = str(x)[:-1] + f", status = {self.mlir_rets[idx]}}}"
            else:
                str_x = str(x)
            ops_str_list.append(str_x)

        ops_str = "\n".join(ops_str_list)
        ops_str = textwrap.indent(ops_str, INDENT_SPACE)
        return f"{repr_head}\n{ops_str}\n{repr_tail}"


class MultiCore(Node):
    def __init__(self, core_id, core_nums, mlir_cmds, indent=0):
        self.core_id = core_id
        self.core_nums = core_nums
        self.mlir_cmds = mlir_cmds
        self.indent = indent
        self.core_split_cmds = []
        self.core_split_rets = []
        self.msges = [Msg()] * 512  # SG2260 has 512 * 14 bits msg que

        last_ret = None
        tmp_cmds = []
        tmp_rets = []

        for cmd_id, mlir_cmd in enumerate(mlir_cmds):
            cmd = mlir_cmd.cmd
            if isinstance(cmd, (tiu_sys, dma_sys)):
                ret = self.consume_sys(cmd)
                if last_ret == Status.PRODUCING and ret == Status.RECIEVING:
                    self.core_split_cmds.append(tmp_cmds)
                    self.core_split_rets.append(tmp_rets)
                    tmp_cmds = []
                    tmp_rets = []
                tmp_cmds.append(mlir_cmds[cmd_id])
                tmp_rets.append(ret)
                last_ret = ret
            else:
                if (
                    last_ret == Status.RECIEVING
                    or last_ret == Status.CONSUMED
                    or last_ret == Status.OP
                ):
                    tmp_cmds.append(mlir_cmds[cmd_id])
                    tmp_rets.append(None)
                    last_ret = Status.OP

            if cmd_id == len(mlir_cmds) - 1:
                assert len(tmp_cmds) > 0
                self.core_split_cmds.append(tmp_cmds)
                self.core_split_rets.append(tmp_rets)
                tmp_cmds = []
                tmp_rets = []

        self.msgcores = [
            MsgCore(
                msgcore_id,
                core_nums,
                msgcore_cmds,
                self.core_split_rets[msgcore_id],
                indent,
            )
            for msgcore_id, msgcore_cmds in enumerate(self.core_split_cmds)
        ]

    @staticmethod
    def get_cmd_type(cmd):
        if isinstance(cmd, tiu_sys):
            if cmd.tsk_eu_typ == 8:
                return SYS_TYPE.SEND
            elif cmd.tsk_eu_typ == 9:
                return SYS_TYPE.WAIT
            else:
                raise ValueError(f"cmd type error: {cmd}")
        elif isinstance(cmd, dma_sys):
            if cmd.cmd_special_function == 3:
                return SYS_TYPE.SEND
            elif cmd.cmd_special_function == 4:
                return SYS_TYPE.WAIT
            else:
                raise ValueError(f"cmd type error: {cmd}")
        else:
            raise ValueError(f"cmd type error: {cmd}")

    @staticmethod
    def get_msg_id(cmd):
        if isinstance(cmd, tiu_sys):
            _, attrs, _ = SYS_converter(SG2260Context, cmd)
        elif isinstance(cmd, dma_sys):
            _, attrs, _ = sDMA_sys_converter(SG2260Context, cmd)
        return attrs["msg_id"]

    @staticmethod
    def get_msg_cnt(cmd):
        if isinstance(cmd, tiu_sys):
            _, attrs, _ = SYS_converter(SG2260Context, cmd)
        elif isinstance(cmd, dma_sys):
            _, attrs, _ = sDMA_sys_converter(SG2260Context, cmd)
        return attrs["cnt"]

    def consume_sys(self, cmd):
        sys = (tiu_sys, dma_sys)
        assert isinstance(cmd, sys)
        if MultiCore.get_cmd_type(cmd) == SYS_TYPE.SEND:
            return self.consume_send(cmd)
        elif MultiCore.get_cmd_type(cmd) == SYS_TYPE.WAIT:
            return self.consume_wait(cmd)

    def consume_send(self, cmd):
        msg_id = MultiCore.get_msg_id(cmd)
        self.msges[msg_id].sent_cnt += 1
        if self.msges[msg_id].remain_wait_cnt == 0:
            self.msges[msg_id].remain_wait_cnt = int(
                MultiCore.get_msg_cnt(cmd) / self.core_nums
            )
        else:
            assert self.msges[msg_id].remain_wait_cnt == int(
                MultiCore.get_msg_cnt(cmd) / self.core_nums
            )
        return Status.PRODUCING

    def consume_wait(self, cmd):
        msg_id = MultiCore.get_msg_id(cmd)
        if (
            int(MultiCore.get_msg_cnt(cmd) / self.core_nums)
            != self.msges[msg_id].sent_cnt
        ):
            return Status.WAITING
        else:
            self.msges[msg_id].remain_wait_cnt -= 1
            if self.msges[msg_id].remain_wait_cnt == 0:
                self.msges[msg_id].sent_cnt = 0
                return Status.CONSUMED
            else:
                return Status.RECIEVING

    def __str__(self):
        return "\n".join([str(msgcore) for msgcore in self.msgcores])
