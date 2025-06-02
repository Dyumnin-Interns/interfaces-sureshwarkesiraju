import cocotb
import random
from cocotb.triggers import Timer , RisingEdge , ReadOnly , NextTimeStep , FallingEdge
from cocotb_bus.drivers import BusDriver
from cocotb_coverage.coverage import CoverCross, CoverPoint ,coverage_db
from cocotb_bus.monitors import BusMonitor
import os

#call back function
def cb_fn(actual_value):
    global expected_value
    exp=expected_value.pop(0)
    print(f"Read: {int(actual_value)}, Expected: {exp}")
    assert int(actual_value) == exp, f"Error: Got {int(actual_value)}, expected {exp}"
    

class sig:
    def __init__(self,write_address,write_data,read_address):
        self.write_address = write_address
        self.write_data= write_data
        self.read_address= read_address

@CoverPoint("top.wadd",
            xf=lambda x,y,z:x , bins=[4,5]
            )

@CoverPoint("top.wda",
            xf=lambda x,y,z:y , bins=[0,1]
            )

@CoverPoint("top.radd",
            xf=lambda x,y,z:z , bins=[0,1,2,3]
            )
@CoverCross("top.cross",
            items=["top.wadd","top.wda","top.radd"]
            )
#dummy funciton
def wr_cover(wadd,wda,radd):
    pass


@CoverPoint("top.port.wr.current",
           xf=lambda x:x['current'],
           bins=['IDLE','wrt_read_and_write_rdy_tnx','read_rdy_wrt_tnx','write_rdy_rd_tnx','read_and_write']
           )

@CoverPoint("top.port.wr.previous",
           xf=lambda x:x['previous'],
           bins=['IDLE','wrt_read_and_write_rdy_tnx','read_rdy_wrt_tnx','write_rdy_rd_tnx','read_and_write']
           )

@CoverCross("top.cross.wr_port.cross",
            items=["top.port.wr.current",
                   "top.port.wr.previous"]
            )

def wr_port_cover(tnx):
    pass



@cocotb.test()
async def dut_test(dut):
    global expected_value
    dut.RST_N.value =1
    await Timer(1,'ns')
    dut.RST_N.value = 0
    
    await Timer(1,'ns')
    await RisingEdge(dut.CLK)

    dut.RST_N.value=1
    expected_value = []
    wrdrv = InputDriver(dut,'',dut.CLK)
    IO_montior(dut,'',dut.CLK,callback=wr_port_cover) 
    #await Timer(1,'ns')
    OutputDriver(dut,'',dut.CLK,cb_fn)       
    #out._driver_send(0)
    for i in range(200):
            wd=random.randint(0,1)
            #wd=1
            #wa=4
            wa=random.randint(4,5)
            ra=random.randint(0,3)
            x=sig(wa,wd,ra)
            #wrdrv._driver_send(x)
            wrdrv.append(x)
            expected_value.append(wd)

            wr_cover(wa,wd,ra)
    await Timer(len(expected_value)*2,'ns')
   

    
    coverage_db.report_coverage(cocotb.log.info,bins=True)
    coverage_file=os.path.join( os.getenv('RESULTS_PATH',"./"),'coverage.xml')
    coverage_db.export_to_xml(filename=coverage_file)              
                
           
     

        
        
class InputDriver(BusDriver):
    _signals =['write_rdy','read_rdy','write_en','write_address','write_data','read_en','read_address']
    def __init__(self,dut,name,clk):
        BusDriver.__init__(self,dut,name,clk)
        self.bus.read_en.value=0
        self.bus.write_en.value=0
        self.clk=clk
    async def _driver_send(self,value,sync=True):

        if self.bus.write_rdy.value !=1:
            await RisingEdge(self.bus.write_rdy)
        self.bus.write_en.value=1
        self.bus.write_address.value=value.write_address 
        self.bus.write_data.value = value.write_data 
        await ReadOnly()
        await RisingEdge(self.clk)
        await NextTimeStep()
        self.bus.write_en.value=0

        if self.bus.read_rdy.value !=1:
            await RisingEdge(self.bus.read_rdy)
        
        self.bus.read_en.value=1
        self.bus.read_address.value=value.read_address 
        await ReadOnly()
        await RisingEdge(self.clk)
        await NextTimeStep()
        self.bus.read_en.value=0



class IO_montior(BusMonitor):
    _signals =['write_rdy','read_rdy','write_en','write_address','write_data','read_en','read_address']
    async def _monitor_recv(self):
        fallingedge=FallingEdge(self.clock)
        rdonly=ReadOnly()
        phases={
                0:'IDLE',
                5:'wrt_read_and_write_rdy_tnx',
                7:'read_rdy_wrt_tnx',
                13:'write_rdy_rd_tnx',
                15:'read_and_write'
        }
        prev='IDLE'
        while True:
            await fallingedge
            await rdonly                
            tnx= (self.bus.read_en.value<<3)|(self.bus.read_rdy.value<<2)|(self.bus.write_en.value<<1)|(self.bus.write_rdy.value)
            self._recv({'previous':prev,'current':phases.get(tnx,'NOTHING')})
            prev=phases.get(tnx,'NOT')



class OutputDriver(BusDriver):
    _signals = ['write_rdy', 'read_rdy', 'read_en', 'read_data']

    def __init__(self, dut, name, clk, sb_callback):
        BusDriver.__init__(self, dut, name, clk)
        self.bus.read_en.value = 0
        self.clk = clk
        self.callback = sb_callback
        self._driver_send(0)

    async def _driver_send(self, value, sync=True):
        while True:
            if self.bus.read_rdy.value != 1:
                await RisingEdge(self.bus.read_rdy)
            self.bus.read_en.value = 1
            await ReadOnly()
            self.callback(int(self.bus.read_data.value))
            await RisingEdge(self.clk)
            await NextTimeStep()
            self.bus.read_en.value = 0



