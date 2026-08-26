#!/usr/bin/env python3
"""Audit canonical Splash pixels against the approved reference image.

This final pre-promotion audit verifies that every canonical pixel is contained
in the recovered reference skeleton and measures direct visual support from the
reference HSV values. It also reports all reviewed recovered pixels intentionally
excluded from the canonical candidate. The tool never alters geometry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

HUE_RANGES=((7,30),(34,58),(76,91),(92,118),(126,160))


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("reference",type=Path)
    p.add_argument("recovered_mask",type=Path)
    p.add_argument("canonical_manifest",type=Path)
    p.add_argument("--out",type=Path,required=True)
    return p.parse_args()


def collect(records):
    out=set()
    for item in records:
        for x,y in item.get("pixels",[]): out.add((int(x),int(y)))
    return out


def stats(points,hue_ok,sat,val):
    if not points:
        return {"pixel_count":0,"route_hue_sat55_val35_ratio":0.0,"sat55_val55_ratio":0.0,"mean_saturation":0.0,"mean_value":0.0}
    arr=np.asarray(list(points),dtype=np.int32); xs=arr[:,0]; ys=arr[:,1]
    return {
        "pixel_count":len(points),
        "route_hue_sat55_val35_ratio":round(float(np.mean(hue_ok[ys,xs]&(sat[ys,xs]>=55)&(val[ys,xs]>=35))),6),
        "sat55_val55_ratio":round(float(np.mean((sat[ys,xs]>=55)&(val[ys,xs]>=55))),6),
        "mean_saturation":round(float(np.mean(sat[ys,xs])),3),
        "mean_value":round(float(np.mean(val[ys,xs])),3),
    }


def main():
    args=parse_args();args.out.mkdir(parents=True,exist_ok=True)
    image=cv2.imread(str(args.reference));mask=cv2.imread(str(args.recovered_mask),cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None: raise SystemExit("Cannot read reference or recovered mask")
    h,w=image.shape[:2]
    if mask.shape!=(h,w): raise SystemExit("Reference/mask geometry mismatch")
    manifest=json.loads(args.canonical_manifest.read_text(encoding="utf-8"))
    canonical=collect(manifest.get("route_trees",[]))|collect(manifest.get("shared_geometry",[]))|collect(manifest.get("preserved_unowned_geometry",[]))
    sk=skeletonize(mask>0); ys,xs=np.where(sk); recovered={(int(x),int(y)) for y,x in zip(ys,xs)}
    outside=canonical-recovered; excluded=recovered-canonical
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);hue,sat,val=cv2.split(hsv)
    hue_ok=np.zeros_like(hue,dtype=bool)
    for lo,hi in HUE_RANGES: hue_ok|=(hue>=lo)&(hue<=hi)
    canonical_stats=stats(canonical,hue_ok,sat,val); excluded_stats=stats(excluded,hue_ok,sat,val)
    result={
        "meta":{
            "stage":"CANONICAL_REFERENCE_OVERLAY_AUDIT",
            "reference_size":[w,h],
            "recovered_skeleton_pixel_count":len(recovered),
            "canonical_pixel_count":len(canonical),
            "canonical_pixels_outside_recovered_skeleton":len(outside),
            "reviewed_excluded_recovered_pixel_count":len(excluded),
            "canonical_visual_support":canonical_stats,
            "excluded_visual_support":excluded_stats,
            "overlay_structurally_exact":len(outside)==0,
            "canonical_promoted":False,
            "splash_reconstruction_allowed":False,
            "next_gate":"canonical manifest promotion" if not outside else "repair canonical pixel provenance",
        },
        "canonical_pixels_outside_recovered_skeleton":[list(p) for p in sorted(outside,key=lambda p:(p[1],p[0]))],
        "reviewed_excluded_recovered_pixels":[list(p) for p in sorted(excluded,key=lambda p:(p[1],p[0]))],
    }
    (args.out/"canonical_reference_overlay_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    overlay=image.copy()
    for x,y in canonical: overlay[y,x]=(255,255,255)
    for x,y in excluded: overlay[y,x]=(0,0,255)
    cv2.imwrite(str(args.out/"canonical_reference_overlay.png"),overlay)
    print(json.dumps(result["meta"],indent=2))
    if outside: raise SystemExit("Canonical pixels exist outside recovered reference skeleton")

if __name__=="__main__": main()
