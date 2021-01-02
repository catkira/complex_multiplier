import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from cocotb.triggers import RisingEdge, ReadOnly
from fixedpoint import FixedPoint
from cocotbext.axi import AxiStreamFrame, AxiStreamSource, AxiStreamSink, AxiStreamMonitor
from collections import deque

import random
import warnings
import os
import logging
import cocotb_test.simulator
import pytest

with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from cocotb.generators.byte import random_data, get_bytes

import importlib.util

CLK_PERIOD_NS = 100


class TB(object):
    def __init__(self,dut):
        self.dut = dut
        self.input_width_a = int(dut.INPUT_WIDTH_A.value)
        self.input_width_b = int(dut.INPUT_WIDTH_B.value)
        self.output_width = int(dut.OUTPUT_WIDTH.value)
        self.stages = int(dut.STAGES.value)
        
        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)        
        
        tests_dir = os.path.abspath(os.path.dirname(__file__))
        model_dir = os.path.abspath(os.path.join(tests_dir, '../model/complex_multiplier_model.py'))
        print(model_dir)
        spec = importlib.util.spec_from_file_location("complex_multiplier_model", model_dir)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        self.model = foo.Model(self.input_width_a,self.input_width_b,self.output_width) 

        
        cocotb.fork(Clock(dut.clk, CLK_PERIOD_NS, units='ns').start())
        
        #self.source = AxiStreamSource(dut, "s_axis_a", dut.clk, dut.rst)
        self.sink = AxiStreamSink(dut, "m_axis", dut.clk)        
        #self.monitor = AxiStreamMonitor(dut, "m_axis", dut.clk)
        
    async def cycle_reset(self):
        self.dut.nrst.setimmediatevalue(1)
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.nrst <= 0
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.nrst <= 1
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)


# Test single multiplication
@cocotb.test()
async def single_multiplication_(dut):
    """Perform a single multiplication of two complex numbers

    Expected Results:
        a*b = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    """
    tb = TB(dut)
    await tb.cycle_reset()
    
    a_bytes = get_bytes(int(tb.input_width_a/8),random_data())
    b_bytes = get_bytes(int(tb.input_width_b/8),random_data())

    # send data, ignore tready
    dut.s_axis_a_tdata <= int.from_bytes(a_bytes, byteorder='big', signed=False)
    dut.s_axis_a_tvalid <= 1    
    dut.s_axis_b_tdata <= int.from_bytes(b_bytes, byteorder='big', signed=False)
    dut.s_axis_b_tvalid <= 1    
    await RisingEdge(dut.clk)
    dut.s_axis_a_tvalid <= 0
    dut.s_axis_b_tvalid <= 0    
        
    rx_frame = await tb.sink.recv()
    receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='big', length=int(tb.output_width/8))
    print(receivedData.hex())
    received_r = receivedData[int(len(receivedData)/2):len(receivedData)]
    received_i = receivedData[0:int(len(receivedData)/2)]

    calculatedData = tb.model.calculate(a_bytes,b_bytes)
    calculated_i = calculatedData[0:int(tb.output_width/8/2)]
    calculated_r = calculatedData[int(tb.output_width/8/2):int(tb.output_width/8)]
    assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                           (int.from_bytes(calculated_r,byteorder='big',signed=True),int.from_bytes(received_r,byteorder='big',signed=True)))
    assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                           (int.from_bytes(calculated_i,byteorder='big',signed=True),int.from_bytes(received_i,byteorder='big',signed=True)))
    assert calculatedData == receivedData, ("Error, expected %s got %s" % (calculatedData.hex(), receivedData.hex()))
    await RisingEdge(dut.clk)
    #dut._log.info("0x%08X * 0x%08X" % (A, B))

# Test multiple multiplications
@cocotb.test()
async def multiple_multiplications_(dut):
    tb = TB(dut)    
    await tb.cycle_reset()
    #tb.sink.queue = deque() # remove remaining items from last test    
    test_frames = []
    for i in range(20):
        a_bytes = get_bytes(int(tb.input_width_a/8),random_data())
        b_bytes = get_bytes(int(tb.input_width_b/8),random_data())
        
        # send data, ignore tready
        dut.s_axis_a_tdata <= int.from_bytes(a_bytes, byteorder='big', signed=False)
        dut.s_axis_a_tvalid <= 1
        dut.s_axis_b_tdata <= int.from_bytes(b_bytes, byteorder='big', signed=False)
        dut.s_axis_b_tvalid <= 1
        test_frame = AxiStreamFrame([a_bytes,b_bytes])
        test_frames.append(test_frame)
        await RisingEdge(dut.clk)
        
    dut.s_axis_a_tvalid <= 0
    dut.s_axis_b_tvalid <= 0
    await RisingEdge(dut.clk)    

    for test_frame in test_frames:
        rx_frame = await tb.sink.recv()
        receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='big', length=int(tb.output_width/8), signed=False)
        received_r = receivedData[int(len(receivedData)/2):len(receivedData)]
        received_i = receivedData[0:int(len(receivedData)/2)]

        calculatedData = tb.model.calculate(test_frame.tdata[0],test_frame.tdata[1])
        calculated_i = calculatedData[0:int(tb.output_width/8/2)]
        calculated_r = calculatedData[int(tb.output_width/8/2):int(tb.output_width/8)]
        assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                            (int.from_bytes(calculated_r,byteorder='big',signed=True),int.from_bytes(received_r,byteorder='big',signed=True)))
        assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                            (int.from_bytes(calculated_i,byteorder='big',signed=True),int.from_bytes(received_i,byteorder='big',signed=True)))
        assert calculatedData == receivedData, ("Error, expected %s got %s" % (calculatedData.hex(), receivedData.hex()))
        await RisingEdge(dut.clk)
        
# cocotb-test

tests_dir = os.path.abspath(os.path.dirname(__file__))
rtl_dir = os.path.abspath(os.path.join(tests_dir, '..', 'hdl'))

@pytest.mark.parametrize("input_width_a", [16, 32])
@pytest.mark.parametrize("input_width_b", [16, 32])
@pytest.mark.parametrize("output_width", [8, 16, 32])
@pytest.mark.parametrize("blocking", [1])
@pytest.mark.parametrize("truncate", [1])
def test_complex_multiplier(request, blocking, input_width_a, input_width_b, output_width, truncate):
    dut = "complex_multiplier"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(rtl_dir, f"{dut}.v"),
    ]

    parameters = {}

    parameters['INPUT_WIDTH_A'] = input_width_a
    parameters['INPUT_WIDTH_B'] = input_width_b
    parameters['OUTPUT_WIDTH'] = input_width_a
    parameters['BLOCKING'] = blocking
    parameters['TRUNCATE'] = truncate

    extra_env = {f'PARAM_{k}': str(v) for k, v in parameters.items()}

    sim_build = os.path.join(tests_dir, "sim_build",
        request.node.name.replace('[', '-').replace(']', ''))

    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
        sim_build=sim_build,
        extra_env=extra_env,
    )

        
