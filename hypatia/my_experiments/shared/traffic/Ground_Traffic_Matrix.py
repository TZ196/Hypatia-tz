import pandas as pd
import Temprol_module as tem
import Spatial_module as spm
import random
import math
import collections

class Node():
    def __init__(self,val = None):
        self.val = val      
        self.children = []   
    def add_child(self,node):
        self.children.append(node)
        
GEANT_Normalized = [0.666375187, 0.618642091, 0.590977571, 0.563213085, 0.541584313, 0.533839914,
                    0.583266097, 0.667692083, 0.791995807, 0.888743851, 0.933041611, 0.981479064,
                    0.972636759, 0.990605207, 1.000000000, 0.950194854, 0.942922186, 0.881275688,
                    0.858416879, 0.834937010, 0.819007020, 0.810132998, 0.738902802, 0.691278814]

ground_coor_path = 'D:\\STK_Files\\traffic_generator\\traffic_generator\\coor_station.xlsx'
coordinate = pd.read_excel(ground_coor_path, usecols=['lat', 'lon'])
save_ground_path = 'D:\\STK_Files\\traffic_generator\\traffic_generator\\地面站流量\\'

n_ter = coordinate.shape[0]  
offerload = 0.1   
band = 1024     
global_time = 1000  

demand = offerload*band*n_ter  

second = []    

for j in range(global_time):
    zone_stat_val_list = []
    zone_weight = tem.calculate_zone_weight(g_time=j, norm_traffic=GEANT_Normalized)
    zone_traffic = [i * demand for i in zone_weight]  
    zone_density = spm.cal_stat_density(coordinate=coordinate)
    for i in range(24):
        zone_stat_value = spm.get_randomflow(total=zone_traffic[i], num=zone_density[i], time=j)
        zone_stat_value = collections.deque(zone_stat_value)
        zone_stat_val_list.append(zone_stat_value)
    destination = []     
    traffic_value = []   
    for i in range(coordinate.shape[0]):
        coor = coordinate.loc[i]
        lat, lon = tem.coord_trans(lat=coor['lat'], lon=coor['lon'])
        time_zone = math.floor(lon / 15) 
        value = zone_stat_val_list[time_zone].popleft()
        OringinNode=Node(i)
        Des_number=random.randint(1,3)
        for des_count in range(0,Des_number):
            des_time_zone = time_zone
            while (des_time_zone == time_zone):
                random.seed(None)
                des = random.randint(0, n_ter-1)
                des_coor = coordinate.loc[des]
                lat, lon =tem.coord_trans(lat=des_coor['lat'], lon=des_coor['lon'])
                des_time_zone = math.floor(lon /15)
            DesNode=Node(des)
            OringinNode.add_child(DesNode)
        print(i) 
        print("start")
        
        
        destination.append("*")
        traffic_value.append("*")
        for child in OringinNode.children:  
            print(child.val)
            destination.append(child.val)
            traffic_value.append(value)
        destination.append("/")
        traffic_value.append("/")
        print("end")
        print(value)

    second.append(destination)
    second.append(traffic_value)
    print(len(second))
    # if len(second) == 14400:
    #     hour = math.floor((j+1) / 3600)
    #     hour_path = save_ground_path + '\.' + str(hour) + 'hour.xlsx'
    #     second = list(map(list, zip(*second)))  
    #     df = pd.read_excel(hour_path, header=None)
    #     new_column = pd.DataFrame(second, columns=['des', 'value']*7200)
    #     df = pd.concat([df, new_column], axis=1)
    #     df.to_excel(hour_path, index=False, header=None)
    #     second = []
    if(len(second)==2000):
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        max_rows = max(len(column) for column in second)

        for col_num, column in enumerate(second, start=1):
            for row_num, value in enumerate(column, start=1):
                sheet.cell(row=row_num, column=col_num, value=value)

        output_excel_path = save_ground_path  +'1000.xlsx'
        workbook.save(output_excel_path)
    # if(len(second)==200):
    #     hour_path = save_ground_path  + 'test' + 'hour.xlsx'
    #     second = list(map(list, zip(*second)))  # 转置
    #     df = pd.read_excel(hour_path, header=None)
    #     new_column = pd.DataFrame(second, columns=['des', 'value']*100)
    #     df = pd.concat([df, new_column], axis=1)
    #     df.to_excel(hour_path, index=False, header=None)
    #     second = []