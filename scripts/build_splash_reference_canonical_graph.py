#!/usr/bin/env python3
"""Build a vector/graph manifest from the reviewed canonical Splash pixels.

This stage performs topology-preserving graph compression only. It does not
invent, interpolate, smooth, or move route geometry. Every emitted graph edge is
an ordered walk through measured canonical pixels. Degree-2 runs are compressed
between terminals/junctions while preserving the exact source pixel path.
Singleton reviewed geometry is represented explicitly as an isolated node rather
than being dropped or converted into a synthetic self-edge.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

NEIGHBOURS = ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser()
    p.add_argument("canonical_manifest",type=Path)
    p.add_argument("--out",type=Path,required=True)
    return p.parse_args()


def neighbours(point, pixels):
    x,y=point
    return [(x+dx,y+dy) for dy,dx in NEIGHBOURS if (x+dx,y+dy) in pixels]


def compress_graph(pixels):
    if not pixels:
        return [],[],[],[]
    degree={p:len(neighbours(p,pixels)) for p in pixels}
    isolated=sorted([p for p,d in degree.items() if d==0],key=lambda p:(p[1],p[0]))
    nodes={p for p,d in degree.items() if d!=2 and d!=0}
    if not nodes and not isolated:
        nodes={min(pixels,key=lambda p:(p[1],p[0]))}
    visited=set(); edges=[]
    for start in sorted(nodes,key=lambda p:(p[1],p[0])):
        for nxt in neighbours(start,pixels):
            key=frozenset((start,nxt))
            if key in visited: continue
            path=[start,nxt]; visited.add(key); prev=start; cur=nxt
            while cur not in nodes:
                opts=[p for p in neighbours(cur,pixels) if p!=prev]
                if not opts: break
                candidate=opts[0]
                visited.add(frozenset((cur,candidate)))
                path.append(candidate); prev,cur=cur,candidate
            edges.append(path)
    terminals=sorted([p for p,d in degree.items() if d==1],key=lambda p:(p[1],p[0]))
    junctions=sorted([p for p,d in degree.items() if d>=3],key=lambda p:(p[1],p[0]))
    return edges,terminals,junctions,isolated


def encode_path(path):
    return [[int(x),int(y)] for x,y in path]


def represented_pixels(edges, isolated):
    result=set(isolated)
    for edge in edges:
        result.update(edge)
    return result


def main():
    args=parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.canonical_manifest.read_text(encoding="utf-8"))
    meta=manifest.get("meta",{})
    if int(meta.get("route_tree_count",0))!=125:
        raise SystemExit("Canonical candidate must contain exactly 125 route trees")
    if meta.get("promotion_blocked"):
        raise SystemExit("Canonical candidate is still promotion-blocked")

    graph_trees=[]; total_edges=0; total_terminals=0; total_junctions=0; total_isolated=0
    unrepresented=[]
    for tree in manifest.get("route_trees",[]):
        tid=int(tree["tree_id"])
        pixels={(int(x),int(y)) for x,y in tree.get("pixels",[])}
        if not pixels: raise SystemExit(f"Tree {tid} has no pixels")
        edges,terminals,junctions,isolated=compress_graph(pixels)
        missing=pixels-represented_pixels(edges,isolated)
        if missing:
            unrepresented.append({"tree_id":tid,"unrepresented_pixel_count":len(missing)})
        total_edges+=len(edges); total_terminals+=len(terminals); total_junctions+=len(junctions); total_isolated+=len(isolated)
        graph_trees.append({
            "tree_id":tid,
            "pin_id":tree.get("pin_id"),
            "side":tree.get("side"),
            "pin":tree.get("pin"),
            "seed":tree.get("seed"),
            "pixel_count":len(pixels),
            "edge_count":len(edges),
            "terminal_count":len(terminals),
            "junction_count":len(junctions),
            "isolated_node_count":len(isolated),
            "terminals":[list(p) for p in terminals],
            "junctions":[list(p) for p in junctions],
            "isolated_nodes":[list(p) for p in isolated],
            "edges":[{"edge_id":f"tree-{tid:03d}-edge-{i+1:03d}","path":encode_path(path),"pixel_count":len(path)} for i,path in enumerate(edges)],
        })

    def semantic_graph(records,kind):
        result=[]
        for index,item in enumerate(records,start=1):
            pixels={(int(x),int(y)) for x,y in item.get("pixels",[])}
            edges,terminals,junctions,isolated=compress_graph(pixels)
            missing=pixels-represented_pixels(edges,isolated)
            if missing:
                raise SystemExit(f"{kind} geometry {item.get('region')} has unrepresented pixels")
            result.append({
                "id":item.get("region",f"{kind}-{index:03d}"),
                "kind":kind,
                "target_trees":item.get("target_trees",[]),
                "reason":item.get("reason"),
                "pixel_count":len(pixels),
                "edges":[{"edge_id":f"{kind}-{index:03d}-edge-{i+1:03d}","path":encode_path(path)} for i,path in enumerate(edges)],
                "terminals":[list(p) for p in terminals],
                "junctions":[list(p) for p in junctions],
                "isolated_nodes":[list(p) for p in isolated],
            })
        return result

    shared=semantic_graph(manifest.get("shared_geometry",[]),"shared")
    unowned=semantic_graph(manifest.get("preserved_unowned_geometry",[]),"unowned")
    result={
        "meta":{
            "stage":"CANONICAL_GRAPH_CANDIDATE",
            "source_of_truth":"reviewed canonical pixel manifest",
            "route_tree_count":len(graph_trees),
            "total_tree_edge_count":total_edges,
            "total_tree_terminal_count":total_terminals,
            "total_tree_junction_count":total_junctions,
            "total_tree_isolated_node_count":total_isolated,
            "shared_geometry_count":len(shared),
            "preserved_unowned_geometry_count":len(unowned),
            "unrepresented_tree_count":len(unrepresented),
            "canonical_promoted":False,
            "splash_reconstruction_allowed":False,
            "promotion_gate":"zero unrepresented trees + raster roundtrip audit + reference overlay audit",
        },
        "route_trees":graph_trees,
        "shared_geometry":shared,
        "preserved_unowned_geometry":unowned,
        "unrepresented_trees":unrepresented,
    }
    (args.out/"canonical_graph_candidate.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result["meta"],indent=2))
    if unrepresented:
        raise SystemExit("Graph candidate does not represent all canonical tree pixels")

if __name__=="__main__": main()
