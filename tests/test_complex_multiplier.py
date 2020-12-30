import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

import random
import warnings

CLK_PERIOD_NS = 100


class TB(object):
    def __init__(self, dut):
        self.dut = dut

        s_count = int(os.getenv("PARAM_S_COUNT"))
        m_count = int(os.getenv("PARAM_M_COUNT"))

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        cocotb.fork(Clock(dut.clk, 10, units="ns").start())

    async def cycle_reset(self):
        self.dut.rst.setimmediatevalue(0)
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst <= 1
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst <= 0
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
		
		
async def run_test_single_mult(dut):
	while True:
		return
	