import os
import h5py
import shutil
import numpy as np
from iric import *

def update_hydro(rri_dir, nays2dh_dir, pid, qmin):

    # make tlist and qlist from the rri calculation result
    fname = os.path.join(rri_dir, "hydro.txt")
    tlist = []; qlist = []
    with open(fname, mode='r') as f:
        lines = f.readlines()
        for l in lines:
            w = l.strip()
            while '  ' in w:
                w = w.replace('  ', ' ')
            data = w.split(' ')
            tt = float(data[0])
            qq = float(data[pid])

            # limit check
            if qq < qmin:
                qq = qmin
            
            # append
            tlist.append(tt)
            qlist.append(qq)

    # incert t=0 and q at t=0
    tlist.insert(0,0.0)
    qlist.insert(0,qlist[0])
    dumlist = [0.0] * len(qlist)   

    # copy Case1.Input.cgn to Case1.cgn
    src = os.path.join(nays2dh_dir, 'Case1_input.cgn')
    dst = os.path.join(nays2dh_dir, 'Case1.cgn')
    if os.path.exists(src):
        shutil.copy2(src, dst)

    # update case1.cgn for the nays2dh
    fname = os.path.join(nays2dh_dir, "Case1.cgn")
    isw = -1
    with h5py.File(fname, 'r') as file:

        items = file['iRIC']['CalculationConditions'].items()
        for it in items:
            if it[0] == 'discharge_waterlevel':
                isw = 1

    if isw == -1:
        dummy_data = np.linspace(0, 10, 10)
        fid = cg_iRIC_Open(fname, mode=CG_MODE_MODIFY)
        cg_iRIC_Write_Integer(fid, 'i_sec_hour', 1)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'time', dummy_data)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'discharge', dummy_data)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'water_level', dummy_data)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'days', dummy_data)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'ivegegrow', dummy_data)
        cg_iRIC_Write_FunctionalWithName(fid, 'discharge_waterlevel', 'ivegein', dummy_data)
        cg_iRIC_Close(fid)


    with h5py.File(fname, 'r+') as file:
        items = file['iRIC']['CalculationConditions']['discharge_waterlevel'].items()
        for it in items:
            vname, dlist = it
            if ' data' in dlist:
                del dlist[' data']
            
            if vname == "time":
                dlist.create_dataset(' data', data=tlist, maxshape=(None), chunks=(10))

            elif vname == "discharge":
                dlist.create_dataset(' data', data=qlist, maxshape=(None), chunks=(10))

            else:
                dlist.create_dataset(' data', data=dumlist, maxshape=(None), chunks=(10))

    # copy Case1.Input.cgn to Case1.cgn
    src = os.path.join(nays2dh_dir, 'Case1.cgn')
    dst = os.path.join(nays2dh_dir, 'Case1_input.cgn')
    if os.path.exists(src):
        shutil.copy2(src, dst)

    return 0

if __name__ == '__main__':
    update_hydro()