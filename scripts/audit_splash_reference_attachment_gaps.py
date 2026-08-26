#!/usr/bin/env python3
"""Audit physical connectivity gaps for reviewed unique Splash attachments.

Ownership evidence and geometric connectivity are separate concerns. This tool
measures the nearest fragment/tree gap for every unique-owned reconciliation
region and checks whether an existing path through the recovered reference
skeleton can connect the fragment to its target tree without crossing another
owned tree. It never adds pixels and is intended to identify targeted reference
undercoverage before canonical promotion.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

NEIGHBOURS = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("recovered_mask", type=Path)
    p.add_argument("partition_audit", type=Path)
    p.add_argument("reconciliation_audit", type=Path)
    p.add_argument("ownership_contract", type=Path)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def geodesic_partition(skeleton, pins):
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


def reconstruct_regions(skeleton, labels):
    out={}
    for kind,mask in (("conflict",(labels<0).astype(np.uint8)),("unassigned",(skeleton&(labels==0)).astype(np.uint8))):
        count,cc,stats,_=cv2.connectedComponentsWithStats(mask,8); index=0
        for component in range(1,count):
            if int(stats[component,cv2.CC_STAT_AREA])==0: continue
            index+=1; rid=f"{kind}-{index:03d}"; ys,xs=np.where(cc==component)
            out[rid]={(int(x),int(y)) for y,x in zip(ys,xs)}
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


def skeleton_path(region,tree,target_label,skeleton,labels):
    q=deque(region); prev={p:None for p in region}; goal=None
    h,w=skeleton.shape
    while q:
        p=q.popleft()
        if p in tree: goal=p; break
        x,y=p
        for dy,dx in NEIGHBOURS:
            n=(x+dx,y+dy); nx,ny=n
            if not(0<=nx<w and 0<=ny<h and skeleton[ny,nx]) or n in prev: continue
            label=int(labels[ny,nx])
            if label>0 and label!=target_label: continue
            prev[n]=p; q.append(n)
    if goal is None: return []
    path=[]; p=goal
    while p is not None: path.append(p); p=prev[p]
    return path[::-1]


def main():
    args=parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    mask=cv2.imread(str(args.recovered_mask),cv2.IMREAD_GRAYSCALE)
    if mask is None: raise SystemExit("Cannot read recovered mask")
    skeleton=skeletonize(mask>0)
    partition=json.loads(args.partition_audit.read_text(encoding="utf-8"))
    reconciliation=json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    contract=json.loads(args.ownership_contract.read_text(encoding="utf-8"))
    pins=partition.get("pins",[]); trees=partition.get("route_tree_pixels")
    if len(pins)!=125 or not isinstance(trees,dict): raise SystemExit("Partition audit is incomplete")
    labels=geodesic_partition(skeleton,pins); regions=reconstruct_regions(skeleton,labels)
    audit_regions={str(r["id"]):r for r in reconciliation.get("regions",[])}
    if set(regions)!=set(audit_regions): raise SystemExit("Reconstructed region IDs differ from reviewed reconciliation audit")
    unique=contract.get("latest_measured_audit",{}).get("ownership_resolution",{}).get("unique_owner_regions",[])
    records=[]
    for item in unique:
        rid=str(item["region"]); tid=int(item["target_tree"])
        region=regions[rid]; tree={(int(x),int(y)) for x,y in trees[str(tid)]}
        gap,rp,tp=nearest_pair(region,tree); path=skeleton_path(region,tree,tid,skeleton,labels)
        bridge=[p for p in path if p not in region and p not in tree]
        bridge_regions=[]
        for x,y in bridge:
            for candidate,pixels in regions.items():
                if (x,y) in pixels and candidate not in bridge_regions: bridge_regions.append(candidate); break
        records.append({"region":rid,"target_tree":tid,"nearest_gap_px":round(gap,3),"fragment_endpoint":list(rp) if rp else None,"tree_contact":list(tp) if tp else None,"existing_recovered_skeleton_path":bool(path),"bridge_pixel_count":len(bridge),"bridge_regions":bridge_regions,"bridge_pixels":[list(p) for p in bridge]})
    disconnected=[r for r in records if not r["existing_recovered_skeleton_path"] or r["bridge_pixel_count"]>0]
    result={"meta":{"stage":"UNIQUE_ATTACHMENT_PHYSICAL_GAP_AUDIT","unique_attachment_count":len(records),"physically_direct_attachment_count":len(records)-len(disconnected),"attachment_gap_count":len(disconnected),"canonical_promotion_blocked":bool(disconnected)},"attachments":records}
    (args.out/"unique_attachment_gap_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result["meta"],indent=2))

if __name__=="__main__": main()
