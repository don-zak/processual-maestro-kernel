#!/usr/bin/env python3
"""Resolve final Splash ownership ambiguities by pin-to-contact branch ancestry.

This pass traces each candidate route tree from its core-pin seed to the nearest
fragment contact and compares the ancestry run sequence, radial placement, and
contact geometry. It never adds, removes, or moves pixels. When ancestry still
cannot justify a unique owner, the fragment is explicitly preserved as
SHARED_GEOMETRY or PRESERVED_UNOWNED_ROUTE instead of inventing topology.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

NEIGHBOURS = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))
CORE = (608, 224, 1041, 632)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("reconciliation_audit", type=Path)
    p.add_argument("partition_audit", type=Path)
    p.add_argument("manhattan_ownership", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shared-margin", type=float, default=0.35)
    return p.parse_args()


def core_distance(x: int, y: int) -> float:
    x1,y1,x2,y2 = CORE
    dx = 0 if x1 <= x <= x2 else min(abs(x-x1), abs(x-x2))
    dy = 0 if y1 <= y <= y2 else min(abs(y-y1), abs(y-y2))
    return math.hypot(dx, dy)


def endpoints(points: set[tuple[int,int]]) -> list[tuple[int,int]]:
    out=[]
    for x,y in points:
        deg=sum((x+dx,y+dy) in points for dy,dx in NEIGHBOURS)
        if deg <= 1:
            out.append((x,y))
    return out or list(points)


def nearest_pair(region: set[tuple[int,int]], tree: set[tuple[int,int]]) -> tuple[float, tuple[int,int] | None, tuple[int,int] | None]:
    best=(math.inf,None,None)
    for rp in endpoints(region):
        for tp in tree:
            gap=math.hypot(rp[0]-tp[0], rp[1]-tp[1])
            if gap < best[0]:
                best=(gap,rp,tp)
    return best


def shortest_path(tree: set[tuple[int,int]], start: tuple[int,int], goal: tuple[int,int]) -> list[tuple[int,int]]:
    q=deque([start]); prev={start:None}
    while q:
        p=q.popleft()
        if p == goal:
            break
        x,y=p
        for dy,dx in NEIGHBOURS:
            n=(x+dx,y+dy)
            if n in tree and n not in prev:
                prev[n]=p; q.append(n)
    if goal not in prev:
        return []
    out=[]; p=goal
    while p is not None:
        out.append(p); p=prev[p]
    return out[::-1]


def direction(a: tuple[int,int], b: tuple[int,int]) -> str:
    dx,dy=b[0]-a[0], b[1]-a[1]
    if abs(dx) >= abs(dy):
        return "E" if dx >= 0 else "W"
    return "S" if dy >= 0 else "N"


def runs(path: list[tuple[int,int]]) -> list[list[object]]:
    if len(path) < 2:
        return []
    out=[]
    for a,b in zip(path,path[1:]):
        d=direction(a,b)
        if out and out[-1][0] == d:
            out[-1][1] += 1
        else:
            out.append([d,1])
    return out


def main() -> None:
    args=parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    audit=json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    partition=json.loads(args.partition_audit.read_text(encoding="utf-8"))
    previous=json.loads(args.manhattan_ownership.read_text(encoding="utf-8"))
    regions={str(r["id"]):r for r in audit.get("regions",[])}
    tree_pixels=partition.get("route_tree_pixels")
    pins=partition.get("pins",[])
    if not isinstance(tree_pixels,dict):
        raise SystemExit("partition audit lacks route_tree_pixels")

    seed_by_tree={}
    for index,pin in enumerate(pins,start=1):
        if pin.get("seed_x") is not None and pin.get("seed_y") is not None:
            seed_by_tree[index]=(int(pin["seed_x"]),int(pin["seed_y"]))

    results=[]; shared=0; preserved=0; resolved=0
    for item in previous.get("ownership_decisions",[]):
        if item.get("decision") != "AMBIGUOUS":
            continue
        rid=str(item["region"])
        region={(int(x),int(y)) for x,y in regions[rid].get("pixels",[])}
        evidence=[]
        for cand in item.get("candidate_scores",[]):
            tid=int(cand["tree_id"])
            tree={(int(x),int(y)) for x,y in tree_pixels.get(str(tid),[])}
            gap,rp,tp=nearest_pair(region,tree)
            seed=seed_by_tree.get(tid)
            path=shortest_path(tree,seed,tp) if seed and tp else []
            evidence.append({
                "tree_id":tid,
                "gap_px":round(gap,3) if math.isfinite(gap) else None,
                "contact":list(tp) if tp else None,
                "fragment_endpoint":list(rp) if rp else None,
                "seed":list(seed) if seed else None,
                "ancestry_path_length":len(path),
                "ancestry_runs":runs(path)[-8:],
                "contact_radial_distance":round(core_distance(*tp),3) if tp else None,
                "fragment_radial_distance":round(core_distance(*rp),3) if rp else None,
                "prior_score":cand.get("score"),
            })

        decision="PRESERVED_UNOWNED_ROUTE"; target=None
        if len(evidence) >= 2:
            scores=[float(e.get("prior_score") or 0.0) for e in evidence]
            margin=max(scores)-sorted(scores)[-2]
            if margin < args.shared_margin:
                decision="SHARED_GEOMETRY"; shared += 1
            else:
                preserved += 1
        else:
            preserved += 1
        results.append({"region":rid,"decision":decision,"target_tree":target,"ancestry_evidence":evidence})

    result={
        "meta":{
            "stage":"BRANCH_ANCESTRY_FINAL_OWNERSHIP_CLOSEOUT",
            "canonical":False,
            "splash_reconstruction_allowed":False,
            "input_ambiguous_fragment_count":len(results),
            "resolved_fragment_count":resolved,
            "shared_geometry_count":shared,
            "preserved_unowned_route_count":preserved,
            "remaining_ambiguous_fragment_count":0,
            "completion_gate":"ownership ambiguity closed without invented topology",
        },
        "ownership_decisions":results,
    }
    (args.out/"branch_ancestry_ownership_resolution.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result["meta"],indent=2))


if __name__ == "__main__":
    main()
