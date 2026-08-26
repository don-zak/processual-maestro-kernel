#!/usr/bin/env python3
"""Recover only the six reviewed unique-attachment gaps from the reference.

The search is deliberately local and evidence-gated. It may traverse existing
recovered skeleton pixels, chromatic pixels inside the known PCB hue families,
or bright low-saturation anti-aliased pixels. For very dark pixels, acceptance
requires strong saturation and a valid route hue. No synthetic interpolation is
allowed: every recovered pixel must already exist in the approved reference.
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

NEIGHBOURS = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))
HUE_RANGES = ((7,30),(34,58),(76,91),(92,118),(126,160))


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser()
    p.add_argument("reference",type=Path)
    p.add_argument("recovered_mask",type=Path)
    p.add_argument("partition_audit",type=Path)
    p.add_argument("reconciliation_audit",type=Path)
    p.add_argument("ownership_contract",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--search-padding",type=int,default=20)
    return p.parse_args()


def geodesic_partition(skeleton,pins):
    h,w=skeleton.shape; inf=np.iinfo(np.int32).max
    distance=np.full((h,w),inf,np.int32); labels=np.zeros((h,w),np.int32); q=deque()
    for label,pin in enumerate(pins,start=1):
        x,y=int(pin["seed_x"]),int(pin["seed_y"]); distance[y,x]=0; labels[y,x]=label; q.append((y,x,label))
    while q:
        y,x,label=q.popleft()
        if labels[y,x]!=label: continue
        nd=distance[y,x]+1
        for dy,dx in NEIGHBOURS:
            ny,nx=y+dy,x+dx
            if not(0<=ny<h and 0<=nx<w and skeleton[ny,nx]): continue
            if nd<distance[ny,nx]: distance[ny,nx]=nd; labels[ny,nx]=label; q.append((ny,nx,label))
            elif nd==distance[ny,nx] and labels[ny,nx] not in (label,-1): labels[ny,nx]=-1
    return labels


def reconstruct_regions(skeleton,labels):
    out={}
    for kind,mask in (("conflict",(labels<0).astype(np.uint8)),("unassigned",(skeleton&(labels==0)).astype(np.uint8))):
        count,cc,stats,_=cv2.connectedComponentsWithStats(mask,8); index=0
        for component in range(1,count):
            if int(stats[component,cv2.CC_STAT_AREA])==0: continue
            index+=1; ys,xs=np.where(cc==component)
            out[f"{kind}-{index:03d}"]={(int(x),int(y)) for y,x in zip(ys,xs)}
    return out


def endpoints(points):
    result=[]
    for x,y in points:
        degree=sum((x+dx,y+dy) in points for dy,dx in NEIGHBOURS)
        if degree<=1: result.append((x,y))
    return result or list(points)


def nearest_pair(region,tree):
    best=(math.inf,None,None)
    for rp in endpoints(region):
        for tp in tree:
            gap=math.hypot(rp[0]-tp[0],rp[1]-tp[1])
            if gap<best[0]: best=(gap,rp,tp)
    return best


def main():
    args=parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    image=cv2.imread(str(args.reference)); mask=cv2.imread(str(args.recovered_mask),cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None: raise SystemExit("Cannot read reference or recovered mask")
    skeleton=skeletonize(mask>0); h,w=skeleton.shape
    partition=json.loads(args.partition_audit.read_text(encoding="utf-8"))
    reconciliation=json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    contract=json.loads(args.ownership_contract.read_text(encoding="utf-8"))
    pins=partition.get("pins",[]); tree_payload=partition.get("route_tree_pixels")
    if len(pins)!=125 or not isinstance(tree_payload,dict): raise SystemExit("Partition audit incomplete")
    trees={int(k):{(int(x),int(y)) for x,y in v} for k,v in tree_payload.items()}
    labels=geodesic_partition(skeleton,pins); regions=reconstruct_regions(skeleton,labels)
    audited={str(r["id"]):r for r in reconciliation.get("regions",[])}
    if set(regions)!=set(audited): raise SystemExit("Reconstructed regions differ from reviewed audit")

    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV); hue,sat,val=cv2.split(hsv)
    hue_ok=np.zeros_like(hue,dtype=bool)
    for lo,hi in HUE_RANGES: hue_ok|=(hue>=lo)&(hue<=hi)
    standard_chroma=hue_ok&(sat>=35)&(val>=45)
    dark_chroma=hue_ok&(sat>=70)&(val>=30)
    bright_bridge=(val>=105)&(sat<=110)
    allowed=standard_chroma|dark_chroma|bright_bridge

    unique=contract.get("latest_measured_audit",{}).get("ownership_resolution",{}).get("unique_owner_regions",[])
    records=[]; recovered_union=set(); unresolved=[]
    for item in unique:
        rid=str(item["region"]); tid=int(item["target_tree"]); region=regions[rid]; tree=trees[tid]
        gap,rp,tp=nearest_pair(region,tree)
        pad=args.search_padding
        x0=max(0,min(rp[0],tp[0])-pad); x1=min(w,max(rp[0],tp[0])+pad+1)
        y0=max(0,min(rp[1],tp[1])-pad); y1=min(h,max(rp[1],tp[1])+pad+1)
        pq=[]; cost={}; prev={}
        for start in endpoints(region): heapq.heappush(pq,(0.0,start)); cost[start]=0.0; prev[start]=None
        goal=None
        while pq:
            current,(x,y)=heapq.heappop(pq)
            if current!=cost[(x,y)]: continue
            if (x,y) in tree: goal=(x,y); break
            for dy,dx in NEIGHBOURS:
                nx,ny=x+dx,y+dy; pt=(nx,ny)
                if not(x0<=nx<x1 and y0<=ny<y1): continue
                label=int(labels[ny,nx])
                if label>0 and label!=tid and pt not in region: continue
                if pt not in region and pt not in tree and not skeleton[ny,nx] and not allowed[ny,nx]: continue
                if skeleton[ny,nx]: pixel_cost=.05
                elif standard_chroma[ny,nx]: pixel_cost=.25
                elif dark_chroma[ny,nx]: pixel_cost=.40
                else: pixel_cost=.80
                step=1.414 if dx and dy else 1.0; new_cost=current+step*pixel_cost
                if new_cost<cost.get(pt,math.inf): cost[pt]=new_cost; prev[pt]=(x,y); heapq.heappush(pq,(new_cost,pt))
        if goal is None:
            unresolved.append(rid); records.append({"region":rid,"target_tree":tid,"nearest_gap_px":round(gap,3),"recovered":False}); continue
        path=[]; point=goal
        while point is not None: path.append(point); point=prev[point]
        path=path[::-1]; new_pixels=[p for p in path if not skeleton[p[1],p[0]]]
        for p in new_pixels: recovered_union.add(p)
        bridge_regions=[]
        for p in path:
            if p in region or p in tree: continue
            for candidate,pixels in regions.items():
                if p in pixels and candidate not in bridge_regions: bridge_regions.append(candidate); break
        records.append({
            "region":rid,"target_tree":tid,"nearest_gap_px":round(gap,3),"recovered":True,
            "new_reference_pixel_count":len(new_pixels),"new_reference_pixels":[list(p) for p in new_pixels],
            "existing_bridge_regions":bridge_regions,"path":[list(p) for p in path],
        })

    recovered_mask=(mask>0).astype(np.uint8)*255
    for x,y in recovered_union: recovered_mask[y,x]=255
    cv2.imwrite(str(args.out/"reference_route_recovered_mask_targeted.png"),recovered_mask)
    result={"meta":{"stage":"TARGETED_UNIQUE_ATTACHMENT_REFERENCE_RECOVERY","unique_attachment_count":len(unique),"recovered_attachment_count":len(unique)-len(unresolved),"unresolved_attachment_count":len(unresolved),"new_reference_pixel_count":len(recovered_union),"canonical":False,"splash_reconstruction_allowed":False},"attachments":records,"unresolved_regions":unresolved}
    (args.out/"targeted_attachment_recovery_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result["meta"],indent=2))

if __name__=="__main__": main()
