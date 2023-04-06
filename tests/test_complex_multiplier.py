import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiStreamFrame, AxiStreamSource, AxiStreamSink, AxiStreamBus
from collections import deque

import random
import warnings
import os
import logging
import cocotb_test.simulator
import pytest

with warnings.catch_warnings():
    warnings.simplefilter('ignore')

import importlib.util

CLK_PERIOD_NS = 100

def _twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0:
        val = val - (1 << bits)
    return int(val)

class TB(object):
    def __init__(self,dut):
        random.seed(30) # reproducible tests
        self.dut = dut
        self.operand_width_a = int(dut.OPERAND_WIDTH_A.value)
        self.operand_width_b = int(dut.OPERAND_WIDTH_B.value)
        self.operand_width_out = int(dut.OPERAND_WIDTH_OUT.value)
        self.input_width_a = int(dut.OPERAND_WIDTH_A.value)*2
        self.input_width_b = int(dut.OPERAND_WIDTH_B.value)*2
        self.output_width = int(dut.OPERAND_WIDTH_OUT.value)*2
        self.stages = int(dut.STAGES.value)
        self.round_mode = int(dut.ROUND_MODE.value)
        self.byte_aligned = int(dut.BYTE_ALIGNED.value)

        self.axis_input_width_a = ((self.input_width_a+15)//16)*16
        self.axis_input_width_b = ((self.input_width_b+15)//16)*16
        self.axis_output_width  = ((self.output_width+15)//16)*16

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)        
        
        tests_dir = os.path.abspath(os.path.dirname(__file__))
        model_dir = os.path.abspath(os.path.join(tests_dir, '../model/complex_multiplier_model.py'))
        spec = importlib.util.spec_from_file_location("complex_multiplier_model", model_dir)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        self.model = foo.Model(self.operand_width_a, self.operand_width_b, self.operand_width_out,
            self.round_mode, self.byte_aligned) 
        
        cocotb.start_soon(Clock(dut.aclk, CLK_PERIOD_NS, units='ns').start())
        
        if self.byte_aligned:
            self.source_a = AxiStreamSource(AxiStreamBus(dut, "s_axis_a"), dut.aclk, dut.aresetn, reset_active_level = False)
            self.source_b = AxiStreamSource(AxiStreamBus(dut, "s_axis_b"), dut.aclk, dut.aresetn, reset_active_level = False)
            self.sink = AxiStreamSink(AxiStreamBus(dut, "m_axis_dout"), dut.aclk, dut.aresetn, reset_active_level = False,
                byte_lanes=1)
            #self.monitor = AxiStreamMonitor(dut, "m_axis", dut.aclk)

    def frameToIQ(self, rx_frame):
        receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='big', length=self.axis_output_width//8)
        received_r = receivedData[len(receivedData)//2:len(receivedData)]
        received_i = receivedData[0:len(receivedData)//2]
        return [received_i, received_r]

    def frameToBytes(self, rx_frame):
        receivedData = (rx_frame.tdata[0]).to_bytes(byteorder='little', length=self.axis_output_width//8)
        return receivedData[::-1]

    def getRandomIQSample(self, width):
        real = random.randint(-2**(width//2-1)-1, 2**(width//2-1))
        imag = random.randint(-2**(width//2-1)-1, 2**(width//2-1))
        axis_width = ((width+15)//16)*16
        if self.byte_aligned:
            real_bytes = real.to_bytes(length=axis_width//8//2, byteorder='big', signed=True)
            imag_bytes = imag.to_bytes(length=axis_width//8//2, byteorder='big', signed=True)
            sample = real_bytes
            sample += imag_bytes
        else:
            op_width = width // 2
            sample = (((imag & (2 ** op_width - 1)) << op_width)) + (real & (2 ** op_width - 1))
        return sample
        
    async def cycle_reset(self):
        self.dut.aresetn.setimmediatevalue(1)
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn.value = 0
        await RisingEdge(self.dut.aclk)
        self.dut.aresetn.value = 1
        await RisingEdge(self.dut.aclk)


# Test single multiplication
@cocotb.test()
async def single_multiplication_(dut):
    """Perform a single multiplication of two complex numbers

    Expected Results:
        a*b = (a_r*b_r - a_i*b_i) + j(a_r*b_i + a_i*b_r)
    """
    tb = TB(dut)
    tb.dut.s_axis_a_tvalid.value = 0
    tb.dut.s_axis_b_tvalid.value = 0
    await tb.cycle_reset()

    if tb.byte_aligned:
        a_bytes = tb.getRandomIQSample(tb.input_width_a)
        b_bytes = tb.getRandomIQSample(tb.input_width_b)

        # send data, ignore tready
        tb.dut.rounding_cy.value = 0
        await tb.source_a.send(AxiStreamFrame(a_bytes[::-1]))
        await tb.source_b.send(AxiStreamFrame(b_bytes[::-1]))

        rx_frame = await tb.sink.recv()
        byte_order = 'big'
        [received_i, received_r] = tb.frameToIQ(rx_frame)

        calculated_data = tb.model.calculate(a_bytes,b_bytes,0)
        calculated_i = calculated_data[0:tb.axis_output_width//8//2]
        calculated_r = calculated_data[tb.axis_output_width//8//2:tb.axis_output_width//8]
        assert received_r == calculated_r, f'real part should have been {int.from_bytes(calculated_r, byteorder=byte_order,signed=True)} but was {int.from_bytes(received_r,byteorder=byte_order,signed=True)}'
        assert received_i== calculated_i, f'imaginary part should have been {int.from_bytes(calculated_i, byteorder=byte_order,signed=True)} but was {int.from_bytes(received_i,byteorder=byte_order,signed=True)}'
        assert calculated_data == tb.frameToBytes(rx_frame), f'Error, expected {calculated_data.hex()} got {tb.frameToBytes(rx_frame).hex()}'
        await RisingEdge(dut.aclk)
    else:
        a_in = tb.getRandomIQSample(tb.input_width_a)
        b_in = tb.getRandomIQSample(tb.input_width_b)

        tb.dut.rounding_cy.value = 0
        tb.dut.s_axis_a_tdata.value = a_in
        tb.dut.s_axis_a_tvalid.value = 1
        tb.dut.s_axis_b_tdata.value = b_in
        tb.dut.s_axis_b_tvalid.value = 1
        await RisingEdge(tb.dut.aclk)
        tb.dut.s_axis_a_tvalid.value = 0
        tb.dut.s_axis_b_tvalid.value = 0

        while tb.dut.m_axis_dout_tvalid.value == 0:
            await RisingEdge(tb.dut.aclk)

        result = tb.dut.m_axis_dout_tdata.value.integer
        # print(f'{result:x}')
        assert result == tb.model.calculate(a_in, b_in, 0)

# Test multiple multiplications
@cocotb.test()
async def multiple_multiplications_(dut):
    tb = TB(dut)
    await tb.cycle_reset()
    rounding_cy = int(os.environ['ROUNDING_CY'])

    if tb.byte_aligned:
        test_data_list = []
        for _ in range(20):
            a_bytes = tb.getRandomIQSample(tb.input_width_a)
            b_bytes = tb.getRandomIQSample(tb.input_width_b)

            tb.dut.rounding_cy.value = rounding_cy
            await tb.source_a.send(AxiStreamFrame(a_bytes[::-1]))
            await tb.source_b.send(AxiStreamFrame(b_bytes[::-1]))
            print(F"rounding_cy send {rounding_cy}")
            test_data = [a_bytes,b_bytes, rounding_cy]
            test_data_list.append(test_data)
            await RisingEdge(dut.aclk)

        dut.s_axis_a_tvalid = 0
        dut.s_axis_b_tvalid = 0
        await RisingEdge(dut.aclk)
        byte_order = 'big'
        for test_data in test_data_list:
            rx_frame = await tb.sink.recv()
            [received_i, received_r] = tb.frameToIQ(rx_frame)

            calculatedData = tb.model.calculate(test_data[0],test_data[1],test_data[2])
            calculated_i = calculatedData[0:tb.axis_output_width//8//2]
            calculated_r = calculatedData[tb.axis_output_width//8//2:tb.axis_output_width//8]
            assert received_r == calculated_r, ("real part should have been %i but was %i " % 
                                (int.from_bytes(calculated_r,byteorder=byte_order,signed=True),int.from_bytes(received_r,byteorder=byte_order,signed=True)))
            assert received_i == calculated_i, ("imaginary part should have been %i but was %i " % 
                                (int.from_bytes(calculated_i,byteorder=byte_order,signed=True),int.from_bytes(received_i,byteorder=byte_order,signed=True)))
            assert calculatedData == tb.frameToBytes(rx_frame), ("Error, expected %s got %s" % (calculatedData.hex(), tb.frameToBytes(rx_frame).hex()))
            await RisingEdge(dut.aclk)
    else:
        a_in = tb.getRandomIQSample(tb.input_width_a)
        b_in = tb.getRandomIQSample(tb.input_width_b)

        num_tx = 20
        tx_count = 0
        rx_count = 0
        test_data_list = []
        while rx_count < num_tx:
            await RisingEdge(tb.dut.aclk)
            if tx_count < num_tx:
                a_in = tb.getRandomIQSample(tb.input_width_a)
                b_in = tb.getRandomIQSample(tb.input_width_b)
                test_data = [a_in, b_in, rounding_cy]
                test_data_list.append(test_data)

                tb.dut.rounding_cy.value = rounding_cy
                tb.dut.s_axis_a_tdata.value = a_in
                tb.dut.s_axis_a_tvalid.value = 1
                tb.dut.s_axis_b_tdata.value = b_in
                tb.dut.s_axis_b_tvalid.value = 1
                tx_count += 1
            
            if tb.dut.m_axis_dout_tvalid.value.integer:
                result = tb.dut.m_axis_dout_tdata.value.integer
                test_data = test_data_list[rx_count]
                assert result == tb.model.calculate(test_data[0], test_data[1], test_data[2])
                rx_count += 1

# cocotb-test

tests_dir = os.path.abspath(os.path.dirname(__file__))
rtl_dir = os.path.abspath(os.path.join(tests_dir, '..', 'hdl'))

@pytest.mark.parametrize("operand_width_a", [16, 20, 32])
@pytest.mark.parametrize("operand_width_b", [16, 32])
@pytest.mark.parametrize("operand_width_out", [32, 22, 16])  # TODO: implement support for 24 bit output
@pytest.mark.parametrize("blocking", [1])
@pytest.mark.parametrize("round_mode", [1, 0])
@pytest.mark.parametrize("stages", [7, 6])
@pytest.mark.parametrize("rounding_cy", [0, 1])
@pytest.mark.parametrize("byte_aligned", [0, 1])
def test_complex_multiplier(blocking, operand_width_a, operand_width_b, operand_width_out, round_mode, stages, rounding_cy, byte_aligned):
    dut = "complex_multiplier"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(rtl_dir, f"{dut}.sv"),
    ]

    parameters = {}

    parameters['OPERAND_WIDTH_A'] = operand_width_a
    parameters['OPERAND_WIDTH_B'] = operand_width_b
    parameters['OPERAND_WIDTH_OUT'] = operand_width_out
    parameters['BLOCKING'] = blocking
    parameters['ROUND_MODE'] = round_mode
    parameters['STAGES'] = stages
    parameters['BYTE_ALIGNED'] = byte_aligned

    parameters_dirname = parameters.copy()
    os.environ['ROUNDING_CY'] = str(rounding_cy)
    parameters_dirname['ROUNDING_CY'] = rounding_cy
    extra_env = {f'PARAM_{k}': str(v) for k, v in parameters_dirname.items()}
    sim_build="sim_build/" + "_".join(("{}={}".format(*i) for i in parameters_dirname.items()))
    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
        sim_build=sim_build,
        extra_env=extra_env,
        waves = True
    )

if __name__ == '__main__':
    # os.environ['SIM'] = 'verilator'
    test_complex_multiplier(blocking = 0, operand_width_a = 20, operand_width_b = 16, operand_width_out = 32,
        round_mode = 1, stages = 6, rounding_cy = 1, byte_aligned = 0)