#!/usr/bin/env python3
"""Generate site/assets/how-pov.json — cinematic PoV-R pipeline Lottie (navy/cyan/gold)."""
import json
W,H,FR,OP=960,420,30,360
CY=[0.133,0.827,0.933,1];GD=[0.961,0.769,0.318,1];RD=[0.973,0.443,0.443,1];GR=[0.204,0.827,0.6,1];NV=[0.063,0.149,0.29,1];SL=[0.58,0.64,0.72,1]
def k(t,v):return {"t":t,"s":v if isinstance(v,list) else [v],"i":{"x":[0.33],"y":[1]},"o":{"x":[0.67],"y":[0]}}
def anim(kf):return {"a":1,"k":kf}
def st(v):return {"a":0,"k":v}
def ks(p,s=None,o=None,r=None):
    return {"o":o or st(100),"r":r or st(0),"p":p if isinstance(p,dict) else st(p+[0]),"a":st([0,0,0]),"s":s or st([100,100,100])}
def pop(t0):return anim([k(t0,[0,0,100]),k(t0+12,[112,112,100]),k(t0+20,[100,100,100])])
def fade(t0,t1=None):
    kf=[k(t0,0),k(t0+10,100)]
    if t1:kf+= [k(t1,100),k(t1+10,0)]
    return anim(kf)
def rect(w,h,r,fill=None,stroke=None,sw=3):
    it=[{"ty":"rc","p":st([0,0]),"s":st([w,h]),"r":st(r)}]
    if fill:it.append({"ty":"fl","c":st(fill),"o":st(100)})
    if stroke:it.append({"ty":"st","c":st(stroke),"o":st(100),"w":st(sw),"lc":2,"lj":2})
    it.append({"ty":"tr","p":st([0,0]),"a":st([0,0]),"s":st([100,100]),"r":st(0),"o":st(100)});return {"ty":"gr","it":it}
def ell(d,fill=None,stroke=None,sw=3):
    it=[{"ty":"el","p":st([0,0]),"s":st([d,d])}]
    if fill:it.append({"ty":"fl","c":st(fill),"o":st(100)})
    if stroke:it.append({"ty":"st","c":st(stroke),"o":st(100),"w":st(sw)})
    it.append({"ty":"tr","p":st([0,0]),"a":st([0,0]),"s":st([100,100]),"r":st(0),"o":st(100)});return {"ty":"gr","it":it}
def line(a,b,col,sw=3,t0=0,dash=False):
    it=[{"ty":"sh","ks":st({"i":[[0,0],[0,0]],"o":[[0,0],[0,0]],"v":[a,b],"c":False})},
        {"ty":"st","c":st(col),"o":st(90),"w":st(sw),"lc":2,"lj":2},
        {"ty":"tm","s":st(0),"e":anim([k(t0,0),k(t0+18,100)]),"o":st(0),"m":1},
        {"ty":"tr","p":st([0,0]),"a":st([0,0]),"s":st([100,100]),"r":st(0),"o":st(100)}]
    return {"ty":"gr","it":it}
L=[];ind=[0]
def layer(name,shapes,ksd,ip=0,op=OP):
    ind[0]+=1;L.append({"ddd":0,"ind":ind[0],"ty":4,"nm":name,"sr":1,"ks":ksd,"ao":0,"shapes":shapes,"ip":ip,"op":op,"st":0,"bm":0})
# stage x positions
X=[110,300,500,690,860];Y=210
# connectors (drawn first = bottom in lottie? lottie: first layer = top). We'll append top-last then reverse.
for i,t in enumerate([40,100,170,250]):
    layer(f"wire{i}",[line([X[i]+50,Y],[X[i+1]-50,Y],CY,3,t)],ks([0,0]))
# 1 AI answer card (problem)
layer("answer",[rect(100,120,14,NV,RD,3),rect(60,8,4,SL),],ks([X[0],Y],pop(0)))
for j,yy in enumerate([-30,-12,6,24]):
    layer(f"ans_line{j}",[rect(64-j*8,6,3,RD if j==2 else SL)],ks([X[0],Y+yy],o=fade(8+j*4)))
# 2 decompose -> micro claims
for j,yy in enumerate([-60,0,60]):
    layer(f"claim{j}",[rect(70,34,10,NV,GD if j==1 else CY,3)],ks([X[1],Y+yy],pop(60+j*8)))
# 3 nodes ring
import math
for j in range(5):
    a=j/5*2*math.pi-math.pi/2;px=X[2]+62*math.cos(a);py=Y+62*math.sin(a)
    t0=120+j*6
    col=anim([k(t0,CY),k(t0+40,CY),k(t0+50,RD if j<4 else GD)])
    layer(f"node{j}",[{"ty":"gr","it":[{"ty":"el","p":st([0,0]),"s":st([30,30])},{"ty":"fl","c":col,"o":st(100)},{"ty":"tr","p":st([0,0]),"a":st([0,0]),"s":st([100,100]),"r":st(0),"o":st(100)}]}],
          ks([px,py],pop(t0)))
layer("node_pulse",[ell(150,None,CY,2)],ks([X[2],Y],anim([k(130,[40,40,100]),k(190,[110,110,100]),k(250,[110,110,100])]),anim([k(130,0),k(140,70),k(190,0)])))
layer("hub",[ell(46,NV,GD,3)],ks([X[2],Y],pop(116)))
# 4 commit/reveal lock -> verdict
layer("lock_body",[rect(70,56,10,NV,GD,3)],ks([X[3],Y+10],pop(190)))
layer("lock_shackle",[{"ty":"gr","it":[{"ty":"sh","ks":st({"i":[[0,0],[0,-20],[0,0]],"o":[[0,-20],[0,0],[0,0]],"v":[[-18,-18],[0,-44],[18,-18]],"c":False})},{"ty":"st","c":st(GD),"o":st(100),"w":st(5),"lc":2},{"ty":"tr","p":st([0,0]),"a":st([0,0]),"s":st([100,100]),"r":st(0),"o":st(100)}]}],
      ks(anim([k(200,[X[3],Y+10,0]),k(230,[X[3],Y+10,0]),k(242,[X[3],Y-2,0])]),o=fade(196)))
layer("verdict_x",[line([-14,-14],[14,14],RD,6,236),line([14,-14],[-14,14],RD,6,240)],ks([X[3],Y+12]))
# 5 receipt on solana + rewards
layer("receipt",[rect(96,130,12,NV,GR,3)],ks([X[4],Y],pop(262)))
for j,yy in enumerate([-38,-18,2]):
    layer(f"rc_line{j}",[rect(60,6,3,GR if j==0 else SL)],ks([X[4],Y+yy],o=fade(272+j*4)))
layer("check",[line([-14,0],[-4,12],GR,6,284),line([-4,12],[18,-14],GR,6,290)],ks([X[4],Y+38]))
for j in range(3):
    layer(f"coin{j}",[ell(22,GD)],ks(anim([k(300+j*6,[X[4],Y+70,0]),k(330+j*6,[X[4]-40+j*40,Y+150,0])]),o=anim([k(300+j*6,0),k(306+j*6,100),k(345,100),k(355,0)])))
L.reverse()
for i,l in enumerate(L):l["ind"]=i+1
json.dump({"v":"5.7.4","fr":FR,"ip":0,"op":OP,"w":W,"h":H,"nm":"AegisAI PoV-R pipeline","ddd":0,"assets":[],"layers":L},open("site/assets/how-pov.json","w"),separators=(",",":"))
print("ok",len(L))
