from fixedpoint import FixedPoint

class Model:
    def __init__(self, operand_width_a, operand_width_b, operand_width_out , round_mode):
        self.operand_width_a = operand_width_a
        self.operand_width_b = operand_width_b
        self.operand_width_out = operand_width_out
        self.round_mode = round_mode

        self.axis_input_width_a = ((self.operand_width_a+7)//8)*8*2
        self.axis_input_width_b = ((self.operand_width_b+7)//8)*8*2
        self.axis_output_width  = ((self.operand_width_out+7)//8)*8*2        

    def calculate(self, a, b, rounding_cy=0):
        signFlag = True
        byteOrder = 'big'
        bitOrder = 'big'
        # endian parameter fir BitArray seems to matter only for bits but not for bytes
        # so bytes have to be reversed manually here
        # use FixPoint to select the used bits
        a_i = FixedPoint(int.from_bytes(a[0:self.axis_input_width_a//2//8],byteorder='big', signed=signFlag), signed=signFlag,m=self.axis_input_width_a//2,n=0)
        a_r = FixedPoint(int.from_bytes(a[self.axis_input_width_a//2//8:],byteorder='big', signed=signFlag), signed=signFlag,m=self.axis_input_width_a//2,n=0)
        b_i = FixedPoint(int.from_bytes(b[0:self.axis_input_width_b//2//8],byteorder='big', signed=signFlag), signed=signFlag,m=self.axis_input_width_b//2,n=0)
        b_r = FixedPoint(int.from_bytes(b[self.axis_input_width_b//2//8:],byteorder='big', signed=signFlag), signed=signFlag,m=self.axis_input_width_b//2,n=0)
        r_r_full = int(a_r*b_r) - int(a_i*b_i)
        r_i_full = int(a_r*b_i) + int(a_i*b_r)
        
        # truncate
        # its important to do truncation after the + and - operation, 
        # if truncation is done before that, the result is slightly different!
        truncate_bits = (self.operand_width_a + self.operand_width_b + 1 - self.operand_width_out)
        if self.round_mode == 0:
            r_r = r_r_full >> truncate_bits
            r_i = r_i_full >> truncate_bits
        else: 
            # rounding by adding 0.5 (round half up) or 0.49999 (round half down) depending on rounding_cy followed by truncation
            biasCorrectionString = "0b"
            for _ in range(self.operand_width_a + self.operand_width_b + 1 - (truncate_bits)):
                biasCorrectionString += "0"
            if rounding_cy:
                biasCorrectionString += "1"
                for _ in range(truncate_bits-1):
                    biasCorrectionString += "0"
            else:
                biasCorrectionString += "0"
                for _ in range(truncate_bits-1):
                    biasCorrectionString += "1"

            biasCorrectionNumber = FixedPoint(biasCorrectionString, signed=True,m=self.operand_width_a + self.operand_width_b + 1,n=0)
            #print(F"r_r = {r_r_full} + {biasCorrectionNumber} >> {truncate_bits} = {(r_r_full + biasCorrectionNumber) >> truncate_bits}   cy = {rounding_cy}")
            r_r = (r_r_full + biasCorrectionNumber) >> truncate_bits
            r_i = (r_i_full + biasCorrectionNumber) >> truncate_bits
        
        #print(F"rounding error = {int(abs(r_r_full>> truncate_bits)) - int(abs(r_r))}")
        r_r = int(FixedPoint(r_r,m=self.operand_width_out,signed=signFlag,overflow_alert='ignore',overflow='wrap'))
        r_i = int(FixedPoint(r_i,m=self.operand_width_out,signed=signFlag,overflow_alert='ignore'))
        r_bytes = r_r.to_bytes(byteorder=byteOrder,length=self.axis_output_width//8//2,signed=signFlag)
        i_bytes = r_i.to_bytes(byteorder=byteOrder,length=self.axis_output_width//8//2,signed=signFlag)
        result = bytearray(i_bytes)
        result += r_bytes
        # print("(%i + j%i) * (%i + j%i) = (%i + j%i)"%(a_r,a_i,b_r,b_i,r_r,r_i))
        # print("(%s) * (%s) = %s"%(a.hex(),b.hex(),result.hex()))
        return result
