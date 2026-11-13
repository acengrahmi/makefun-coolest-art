#!/usr/bin/env python3
"""
Make the coolest art - make.fun bounty entry.
Bold retro synthwave / cyber sunset: neon sun with scanline cuts,
silhouette mountains, chrome perspective grid, stars, strong contrast.
Pure Python stdlib only. Manual PNG encoder (zlib + struct).
Deterministic: fixed hash-based stars, no randomness, no timestamps.
"""
import sys
import os
import math
import zlib
import struct

W = 800
H = 800
HORIZON = 520

fb = bytearray(W * H * 3)

def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        fb[i] = r; fb[i+1] = g; fb[i+2] = b

def blend_px(x, y, r, g, b, a):
    if 0 <= x < W and 0 <= y < H and a > 0:
        if a >= 1.0:
            set_px(x, y, r, g, b); return
        i = (y * W + x) * 3
        inv = 1.0 - a
        fb[i]   = int(fb[i] * inv + r * a)
        fb[i+1] = int(fb[i+1] * inv + g * a)
        fb[i+2] = int(fb[i+2] * inv + b * a)

def filled_circle(cx, cy, r, color, soft=1.2):
    cr, cg, cb = color
    for y in range(max(0,int(cy-r-2)), min(H,int(cy+r+3))):
        for x in range(max(0,int(cx-r-2)), min(W,int(cx+r+3))):
            d = math.hypot(x-cx, y-cy)
            if d <= r - soft:
                set_px(x, y, cr, cg, cb)
            elif d <= r + soft:
                blend_px(x, y, cr, cg, cb, (r+soft-d)/(2*soft))

def circle_alpha(cx, cy, r, color, alpha):
    cr, cg, cb = color
    for y in range(max(0,int(cy-r-1)), min(H,int(cy+r+2))):
        for x in range(max(0,int(cx-r-1)), min(W,int(cx+r+2))):
            if math.hypot(x-cx, y-cy) <= r:
                blend_px(x, y, cr, cg, cb, alpha)

def polygon(points, color):
    cr, cg, cb = color
    xs=[p[0] for p in points]; ys=[p[1] for p in points]
    x0=int(min(xs)); x1=int(max(xs)); y0=int(min(ys)); y1=int(max(ys))
    n=len(points)
    for y in range(max(0,y0), min(H,y1+1)):
        for x in range(max(0,x0), min(W,x1+1)):
            inside=False; j=n-1
            for i in range(n):
                xi,yi=points[i]; xj,yj=points[j]
                if ((yi>y)!=(yj>y)) and (x < (xj-xi)*(y-yi)/(yj-yi+1e-9)+xi):
                    inside=not inside
                j=i
            if inside:
                set_px(x,y,cr,cg,cb)

def thick_line(x0,y0,x1,y1,width,color,alpha=1.0):
    steps=int(max(abs(x1-x0),abs(y1-y0)))+1
    r=width/2.0
    for s in range(steps+1):
        t=s/steps if steps else 0
        cx=x0+(x1-x0)*t; cy=y0+(y1-y0)*t
        # small filled circle via bounding box
        for y in range(max(0,int(cy-r-1)), min(H,int(cy+r+2))):
            for x in range(max(0,int(cx-r-1)), min(W,int(cx+r+2))):
                if math.hypot(x-cx,y-cy) <= r:
                    if alpha>=1.0: set_px(x,y,color[0],color[1],color[2])
                    else: blend_px(x,y,color[0],color[1],color[2],alpha)

def rect(x0,y0,x1,y1,color):
    for y in range(max(0,y0), min(H,y1)):
        for x in range(max(0,x0), min(W,x1)):
            set_px(x,y,color[0],color[1],color[2])

def lerp(c1,c2,t):
    return (int(c1[0]+(c2[0]-c1[0])*t), int(c1[1]+(c2[1]-c1[1])*t), int(c1[2]+(c2[2]-c1[2])*t))

def hash2(x,y):
    # deterministic pseudo-random 0..1 from coords
    v = math.sin(x*127.1 + y*311.7) * 43758.5453
    return v - math.floor(v)

# ---------- Scene ----------
def draw():
    # Sky gradient: deep indigo -> purple -> magenta, down to horizon
    sky_stops = [(0.0,(8,4,32)), (0.35,(38,10,68)), (0.62,(92,20,110)),
                 (0.82,(196,42,120)), (1.0,(255,110,80))]
    for y in range(HORIZON):
        t = y/(HORIZON-1)
        # find segment
        for i in range(len(sky_stops)-1):
            t0,c0 = sky_stops[i]; t1,c1 = sky_stops[i+1]
            if t0 <= t <= t1:
                col = lerp(c0,c1,(t-t0)/(t1-t0)); break
        else:
            col = sky_stops[-1][1]
        base=y*W*3
        for x in range(W):
            i=base+x*3; fb[i]=col[0]; fb[i+1]=col[1]; fb[i+2]=col[2]
    # Ground base: near-black purple
    for y in range(HORIZON, H):
        t=(y-HORIZON)/(H-HORIZON)
        col=lerp((26,6,44),(6,2,18),t)
        base=y*W*3
        for x in range(W):
            i=base+x*3; fb[i]=col[0]; fb[i+1]=col[1]; fb[i+2]=col[2]

    # Stars (deterministic hash grid, only upper sky, fade near horizon)
    for gy in range(0, 26):
        for gx in range(0, 40):
            h1=hash2(gx,gy); h2=hash2(gx+100,gy+50); h3=hash2(gx+7,gy+200)
            if h1 > 0.62:
                sx=int(gx*20 + h2*16); sy=int(gy*16 + h3*12)
                if sy < 400:
                    fade = 1.0 - (sy/430.0)
                    bright = int(120 + 135*h2)
                    sz = 2 if h1>0.90 else 1
                    col=(bright, bright, int(bright*(0.85+0.15*h3)))
                    for dy in range(sz):
                        for dx in range(sz):
                            blend_px(sx+dx, sy+dy, col[0],col[1],col[2], 0.35+0.6*fade)
                    if h1>0.94:  # cross sparkle
                        for d in (-3,-2,2,3):
                            blend_px(sx+d, sy, 200,220,255, 0.5*fade)
                            blend_px(sx, sy+d, 200,220,255, 0.5*fade)

    # Distant city / mountain glow behind sun handled later

    # Sun glow (layered alpha circles)
    for (r,a) in [(250,0.10),(225,0.12),(205,0.14)]:
        circle_alpha(400, 430, r, (255,60,140), a)

    # Sun: circle with vertical gradient yellow->orange->magenta, with horizontal cuts increasing toward bottom
    SUN_CX, SUN_CY, SUN_R = 400, 430, 185
    # cuts: (y_start_relative, thickness)
    cuts = [(28,5),(58,7),(88,10),(116,13),(142,17)]
    for y in range(SUN_CY-SUN_R, SUN_CY+SUN_R):
        if y<0 or y>=HORIZON+40: continue
        dy=y-SUN_CY
        # check cut
        in_cut=False
        for (cy0,th) in cuts:
            if cy0 <= dy < cy0+th:
                in_cut=True; break
        if in_cut: continue
        half=math.sqrt(max(0, SUN_R*SUN_R - dy*dy))
        t=(dy+SUN_R)/(2*SUN_R)  # 0 top -> 1 bottom
        if t<0.5:
            col=lerp((255,230,90),(255,150,50), t*2)
        else:
            col=lerp((255,150,50),(255,45,130), (t-0.5)*2)
        for x in range(int(SUN_CX-half), int(SUN_CX+half)):
            set_px(x,y,col[0],col[1],col[2])

    # Mountains silhouettes (two ranges)
    back = [(0,520),(0,452),(90,404),(170,448),(250,392),(340,452),(430,410),(520,462),(610,398),(700,450),(800,420),(800,520)]
    polygon(back, (42,12,66))
    # neon rim light on back range: draw offset copy top edge lines
    for i in range(len(back)-2):
        thick_line(back[i][0],back[i][1],back[i+1][0],back[i+1][1],2,(255,70,180),alpha=0.85)
    front = [(0,520),(0,478),(120,438),(230,486),(360,446),(480,492),(600,444),(710,484),(800,462),(800,520)]
    polygon(front, (14,4,30))
    for i in range(len(front)-2):
        thick_line(front[i][0],front[i][1],front[i+1][0],front[i+1][1],2,(0,220,255),alpha=0.75)

    # Horizon neon line
    rect(0, HORIZON-2, W, HORIZON+2, (255,45,150))
    rect(0, HORIZON+2, W, HORIZON+4, (0,220,255))

    # Sun reflection shimmer on grid (center column glow)
    for y in range(HORIZON+4, H):
        t=(y-HORIZON)/(H-HORIZON)
        width = 30 + t*180
        a = 0.16*(1-t)+0.04
        col = lerp((255,120,60),(255,45,150), t)
        for x in range(int(400-width), int(400+width)):
            blend_px(x,y,col[0],col[1],col[2],a)

    # Perspective grid: vertical rays from vanishing point
    VPX, VPY = 400, HORIZON
    for i in range(-14, 15):
        x_bottom = VPX + i*92
        col = (0,225,255) if i%2==0 else (200,50,255)
        # glow pass then core pass
        thick_line(VPX, VPY, x_bottom, H, 5, col, alpha=0.28)
        thick_line(VPX, VPY, x_bottom, H, 2, col, alpha=1.0)
    # Horizontal grid lines with exponential spacing (perspective)
    rows=[]
    k=0
    while True:
        yy = HORIZON + int(6*(1.42**k))
        if yy>=H: break
        rows.append(yy); k+=1
    for idx, yy in enumerate(rows):
        th = 2 if idx<6 else 3
        thick_line(0, yy, W, yy, th, (0,225,255), alpha=0.30)  # glow under
        thick_line(0, yy, W, yy, 1 if idx<6 else 2, (140,240,255), alpha=1.0)

    # Foreground geometric accents: two floating chrome triangles / diamonds (bold composition)
    # Left diamond outline neon cyan
    diamond=[(108,168),(148,222),(108,276),(68,222)]
    for i in range(4):
        thick_line(diamond[i][0],diamond[i][1],diamond[(i+1)%4][0],diamond[(i+1)%4][1],6,(0,225,255),alpha=0.35)
        thick_line(diamond[i][0],diamond[i][1],diamond[(i+1)%4][0],diamond[(i+1)%4][1],3,(160,250,255),alpha=1.0)
    # Right triangle outline neon magenta
    tri=[(668,140),(724,238),(612,238)]
    for i in range(3):
        thick_line(tri[i][0],tri[i][1],tri[(i+1)%3][0],tri[(i+1)%3][1],6,(255,45,150),alpha=0.35)
        thick_line(tri[i][0],tri[i][1],tri[(i+1)%3][0],tri[(i+1)%3][1],3,(255,170,220),alpha=1.0)
    # Small filled accent circle top-left
    filled_circle(688, 96, 10, (255,230,90))
    filled_circle(116, 84, 7, (255,255,255))

    # Vignette: darken corners deterministically
    for y in range(H):
        for x in range(W):
            dx=(x-400)/400.0; dy=(y-400)/400.0
            d=dx*dx+dy*dy
            if d>0.85:
                a=min(0.42,(d-0.85)*0.55)
                blend_px(x,y,0,0,10,a)

# ---------- PNG encoder ----------
def png_chunk(typ, data):
    c=struct.pack(">I", len(data))+typ+data
    c+=struct.pack(">I", zlib.crc32(typ+data) & 0xffffffff)
    return c

def write_png(path):
    raw=bytearray()
    for y in range(H):
        raw.append(0)
        s=y*W*3
        raw.extend(fb[s:s+W*3])
    png=b"\x89PNG\r\n\x1a\n"
    png+=png_chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png+=png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png+=png_chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path,"wb") as f:
        f.write(png)

def main():
    out=sys.argv[1] if len(sys.argv)>1 else "/output/entry.png"
    draw()
    write_png(out)

if __name__=="__main__":
    main()
