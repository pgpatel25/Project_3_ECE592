from pathlib import Path
import csv, statistics as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors=['#2463a0','#db7933']
def read(name): return list(csv.DictReader((ROOT/'data'/name).open()))
for folder,stem,title in [('pipline_test','results','Pipeline overlap'),('OoOE_test','results_oooe','Instruction scheduling'),('branch_predictor','results_branch','Branch predictability')]:
 a=read(folder+'_'+stem+'_skylark.csv'); b=read(folder+'_'+stem+'.csv')
 fig,ax=plt.subplots(figsize=(7,3))
 for j,(rows,label) in enumerate([(a,'Skylark'),(b,'Artemisia')]):
  bars=ax.bar([i+(j-.5)*.34 for i in range(len(rows))],[float(r['Time_Seconds']) for r in rows],width=.34,label=label,color=colors[j])
  ax.bar_label(bars,fmt='%.3f',padding=3)
 ax.set_xticks(range(len(a)),[r['Test'] for r in a]); ax.set_ylabel('Elapsed time (s)'); ax.set_ylim(0,max(float(r['Time_Seconds']) for r in a+b)*1.3); ax.legend(fontsize=8); ax.set_title(title+' — one retained timing per condition');fig.tight_layout();fig.savefig(ROOT/'figures'/f'{folder}.pdf');plt.close(fig)
fig,ax=plt.subplots(figsize=(7,3))
for suffix,label in [('_skylark','Skylark'),('','Artemisia')]:
 r=read('instruction_width_results_fetch'+suffix+'.csv');ax.plot([int(v['NOP_Count']) for v in r],[float(v['IPC']) for v in r],'o-',label=label)
ax.set(xlabel='NOPs per loop iteration',ylabel='NOPs / TSC tick');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(ROOT/'figures/fetch.pdf');plt.close(fig)
def curve(host,kind):
 d=defaultdict(list)
 for r in read('prf_'+host+'_'+kind+'.csv'):d[int(r['icount'])].append(float(r['median_tsc']))
 x=sorted(d);return x,[st.median(d[k]) for k in x],[min(d[k]) for k in x],[max(d[k]) for k in x]
for name,kinds in [('rob',['nop']),('prf',['nop','int_add','sse'])]:
 fig,axes=plt.subplots(1,2,figsize=(9,3.4),sharey=True)
 for ax,host,title in zip(axes,['skylark.ece.ncsu.edu','mymachine'],['Skylark: 3 launches / point','Artemisia: 5 launches / point']):
  for kind in kinds:
   x,y,lo,hi=curve(host,kind);line,=ax.plot(x,y,label=kind,lw=1.2);ax.fill_between(x,lo,hi,color=line.get_color(),alpha=.17)
  ax.set(xlabel='Filler instructions between loads',title=title,xlim=(0,400),ylim=(0,1100));ax.grid(alpha=.2);ax.legend(fontsize=8)
 axes[0].set_ylabel('TSC ticks / iteration');fig.tight_layout();fig.savefig(ROOT/'figures'/f'{name}.pdf');plt.close(fig)
