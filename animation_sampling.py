import struct,math,bisect

def unity_euler_quaternion(v):
    # Unity applies Euler rotations in Z, X, Y order: qY * qX * qZ.
    x,y,z=[math.radians(a)/2 for a in v]
    sx,cx,sy,cy,sz,cz=math.sin(x),math.cos(x),math.sin(y),math.cos(y),math.sin(z),math.cos(z)
    return [cy*sx*cz+sy*cx*sz,sy*cx*cz-cy*sx*sz,cy*cx*sz-sy*sx*cz,cy*cx*cz+sy*sx*sz]

def sample_clip(t,paths,allow_missing=False):
    muscle=t['m_MuscleClip']; c=muscle['m_Clip']['data']; stream=c['m_StreamedClip']; dense=c['m_DenseClip']; const=c['m_ConstantClip']['data']
    raw=struct.pack('<%dI'%len(stream['data']),*stream['data']); offset=0; curves=[[] for _ in range(stream['curveCount'])]
    while offset<len(raw):
        time,count=struct.unpack_from('<fI',raw,offset); offset+=8
        for _ in range(count):
            index,*coeff=struct.unpack_from('<I4f',raw,offset); offset+=20
            assert index<len(curves)
            curves[index].append((time,coeff))
    assert offset==len(raw)
    times=[[f[0] for f in curve] for curve in curves]
    start,end=muscle['m_StartTime'],muscle['m_StopTime']
    frames=max(2,math.ceil((end-start)*60)+1); ts=[start+(end-start)*i/(frames-1) for i in range(frames)]
    values=[]
    for tm in ts:
        row=[]
        for curve,ct in zip(curves,times):
            idx=max(0,bisect.bisect_right(ct,tm)-1); kt,coeff=curve[idx]; dt=max(0,tm-kt)
            row.append(((coeff[0]*dt+coeff[1])*dt+coeff[2])*dt+coeff[3] if abs(kt)<1e10 else coeff[3])
        dc=dense['m_CurveCount']
        if dc:
            frame=min(dense['m_FrameCount']-1,max(0,(tm-dense['m_BeginTime'])*dense['m_SampleRate']))
            lo=math.floor(frame); hi=min(lo+1,dense['m_FrameCount']-1); weight=frame-lo
            row.extend(dense['m_SampleArray'][lo*dc+i]*(1-weight)+dense['m_SampleArray'][hi*dc+i]*weight for i in range(dc))
        row.extend(const); values.append(row)
    tracks=[]; off=0; missing=[]
    for b in t['m_ClipBindingConstant']['genericBindings']:
        n={1:3,2:4,3:3,4:3}.get(b['attribute'],1) if b['typeID']==4 else 1
        node=paths.get(b['path'])
        if node is not None and b['typeID']==4 and b['attribute'] in (1,2,3,4):
            samples=[row[off:off+n] for row in values]
            if b['attribute']==4:samples=[unity_euler_quaternion(v) for v in samples]
            if b['attribute'] in (2,4):
                for v in samples:
                    length=math.sqrt(sum(x*x for x in v))
                    assert .5<length<1.5
                    v[:]=[x/length for x in v]
            track={'node':node,'property':{1:'position',2:'quaternion',3:'scale',4:'quaternion'}[b['attribute']],'values':[round(v,7) for sample in samples for v in sample]}
            assert all(math.isfinite(x) for x in track['values'])
            tracks.append(track)
        else: missing.append(b)
        off+=n
    assert off==len(values[0]),(t['m_Name'],off,len(values[0]))
    if not allow_missing:assert not missing,(t['m_Name'],missing[:3])
    return {'name':t['m_Name'],'duration':end-start,'times':[round(x-start,7) for x in ts],'tracks':tracks,'omittedBindings':missing}

