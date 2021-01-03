from fixedpoint import FixedPoint
from bitstring import BitArray

class Model:
    def __init__(self, input_width_a, input_width_b, output_width , truncate):
        self.input_width_a = input_width_a
        self.input_width_b = input_width_b
        self.output_width = output_width
        self.truncate = truncate

    def calculate(self, a, b, rounding_cy=0):
        signFlag = True
        byteOrder = 'big'
        a_i = FixedPoint("0b"+BitArray(a).bin[0:int(self.input_width_a/2)], signed=signFlag,m=self.input_width_a/2,n=0)
        a_r = FixedPoint("0b"+BitArray(a).bin[int(self.input_width_a/2):], signed=signFlag,m=self.input_width_a/2,n=0)
        b_i = FixedPoint("0b"+BitArray(b).bin[0:int(self.input_width_b/2)], signed=signFlag,m=self.input_width_b/2,n=0)
        b_r = FixedPoint("0b"+BitArray(b).bin[int(self.input_width_b/2):], signed=signFlag,m=self.input_width_b/2,n=0)
        r_r = int(a_r*b_r) - int(a_i*b_i)
        r_i = int(a_r*b_i) + int(a_i*b_r)
        
        # truncate
        # its important to do truncation after the + and - operation, 
        # if truncation is done before that, the result is slightly different!
        truncate_bits = self.input_width_a + self.input_width_b - self.output_width
        if self.truncate == 1:
            r_r = r_r >> truncate_bits
            r_i = r_i >> truncate_bits
        else: 
        # truncation with bias correction
            biasCorrectionString = "0b0"
            for i in range(truncate_bits-2):
                biasCorrectionString += "1"
            if (rounding_cy == 1):
                biasCorrectionString += "1"
            else:
                biasCorrectionString += "0"
            biasCorrectionNumber = FixedPoint(biasCorrectionString, signed=False,m=truncate_bits,n=0)
            print(biasCorrectionNumber)
            r_r = (r_r + biasCorrectionNumber) >> truncate_bits
            r_i = (r_i + biasCorrectionNumber) >> truncate_bits
        
        
        r_r = int(FixedPoint(r_r,m=int(self.output_width/2),signed=signFlag,overflow_alert='ignore',overflow='wrap'))
        r_i = int(FixedPoint(r_i,m=int(self.output_width/2),signed=signFlag,overflow_alert='ignore'))
        r_bytes = r_r.to_bytes(byteorder=byteOrder,length=int(self.output_width/8/2),signed=signFlag)
        i_bytes = r_i.to_bytes(byteorder=byteOrder,length=int(self.output_width/8/2),signed=signFlag)
        result = bytearray(i_bytes)
        result += r_bytes
        # print("(%i + j%i) * (%i + j%i) = (%i + j%i)"%(a_r,a_i,b_r,b_i,r_r,r_i))
        # print("(%s) * (%s) = %s"%(a.hex(),b.hex(),result.hex()))
        return result