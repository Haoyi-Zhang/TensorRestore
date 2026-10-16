"""Render restoration, packet and checking relations as direct Python vectors."""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Circle

plt.rcParams.update({"font.family": "STIXGeneral", "font.size": 9.5,
                     "mathtext.fontset": "stix", "text.usetex": False,
                     "pdf.fonttype": 42, "ps.fonttype": 42})
META = {"Creator": "Matplotlib", "CreationDate": None, "ModDate": None}

def canvas(w, h, bounds):
    fig, ax = plt.subplots(figsize=(w/2.54, h/2.54))
    ax.set(xlim=bounds[:2], ylim=bounds[2:])
    ax.axis("off")
    fig.subplots_adjust(left=.01, right=.99, bottom=.02, top=.98)
    return fig, ax

def box(ax, x, y, text, w, h=.85, dashed=False, gray=False):
    ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor=".95" if gray else "white",
                           edgecolor="black",lw=.8,ls="--" if dashed else "-"))
    ax.text(x,y,text,ha="center",va="center",linespacing=1.25)

def arrow(ax, start, end, dashed=False):
    ax.add_patch(FancyArrowPatch(start,end,arrowstyle="-|>",mutation_scale=9,
                                lw=.8,color="black",ls="--" if dashed else "-"))

def packet_fan(out):
    fig,ax=canvas(16,9,(-.1,15.5,-.1,8.2))
    box(ax,1.4,5.5,r"init $h\leftarrow a$",2.7)
    for y,i in [(7,"1"),(5.5,"i"),(4,"k")]:
        box(ax,5.4,y,r"$p_"+i+r"$ atomic"+"\n"+
            r"$o_"+i+r",h\leftarrow y_"+i+r",y_"+i+r"$",3.1,gray=True)
        box(ax,9.7,y,r"$q_"+i+r":h\leftarrow a$",2.6)
        arrow(ax,(2.75,5.5),(3.85,y))
        arrow(ax,(6.95,y),(8.4,y))
        arrow(ax,(11,y),(12.5,5.5))
    box(ax,13.8,5.5,r"$f:o_{k+1}\leftarrow h$",2.6)
    ax.text(.2,2.8,"Dashed lines: effects on shared cell "+r"$h$"+
            " (not order edges)",ha="left",va="center")
    for x,label in zip([2,4.2,6.4,8.6,10.8,13],
                       [r"$p_1$",r"$p_i$",r"$p_k$",r"$q_1$",r"$q_i$",r"$q_k$"]):
        ax.text(x,2.1,label,ha="center",va="center")
        ax.plot([x,7.5],[1.85,1.05],ls="--",lw=.7,color=".4")
    ax.add_patch(Circle((7.5,.75),.3,facecolor="white",edgecolor="black",lw=.8))
    ax.text(7.5,.75,r"$h$",ha="center",va="center")
    ax.text(.2,.25,r"$y_i=a\,\mathrm{xor}\,x_i$",ha="left",va="center")
    fig.savefig(out/"packet-fan.pdf",metadata=META);plt.close(fig)

def restoring(out):
    fig,ax=canvas(10.5,3.8,(-.1,8.8,-1.65,1.65))
    for y,i in [(.85,1),(-.85,2)]:
        box(ax,1.1,y,r"$b_"+str(i)+r":x$",2.0,dashed=True)
        box(ax,4.1,y,r"$g_"+str(i)+r":v$",2.0)
        arrow(ax,(2.1,y),(3.1,y))
        arrow(ax,(5.1,y),(6.3,0))
    box(ax,7.5,0,r"$r$ reads $v$",2.4)
    fig.savefig(out/"restoring-order.pdf",metadata=META);plt.close(fig)

def pipeline(out):
    fig,ax=canvas(16,6.4,(-.1,16.6,-2.7,3.1))
    box(ax,1.65,.9,"Source graph\nTarget DAG + budget",3.2,1.15)
    box(ax,5.5,1.55,"Untrusted\nproducer",2.8,1.0)
    box(ax,5.5,-.1,"Restoration lists\nFlow + optional ideal",3.3,1.0)
    box(ax,10.25,.9,"Certificate checker\nStructure + reads + flow",3.6,1.2,gray=True)
    box(ax,14.65,.9,"Accept / reject\nChecked peak",3.0,1.1)
    box(ax,5.5,-2.0,"Finite oracles and\nnumeric interpreter",3.3,1.0)
    arrow(ax,(3.25,1.1),(4.1,1.55))
    arrow(ax,(5.5,1.05),(5.5,.4))
    arrow(ax,(7.15,-.1),(8.45,.55))
    ax.plot([1.65,1.65,10.25],[1.475,2.6,2.6],color="black",lw=.8)
    arrow(ax,(10.25,2.6),(10.25,1.5))
    arrow(ax,(12.05,.9),(13.15,.9))
    arrow(ax,(1.65,.325),(3.85,-2),dashed=True)
    arrow(ax,(7.15,-2),(8.2,-2),dashed=True)
    ax.text(8.45,-2,"Bounded test instruments\nNot used by acceptance",
            ha="left",va="center",linespacing=1.25)
    fig.savefig(out/"certificate-pipeline.pdf",metadata=META);plt.close(fig)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--outdir",type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();args.outdir.mkdir(parents=True,exist_ok=True)
    for draw in (packet_fan,restoring,pipeline):draw(args.outdir)
