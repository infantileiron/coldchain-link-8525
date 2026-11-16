import math
from scipy.stats import pearsonr,spearmanr
ALGORITHM_VERSION='pearson-spearman-1.0'
def analyze(rows,feature):
 valid=[r for r in rows if r.get(feature) is not None and r.get('loss') is not None]
 x=[r[feature] for r in valid];y=[r['loss'] for r in valid]
 if len(valid)<3:raise ValueError('有效配对不足 3 条，补齐样本后重新创建研究')
 if len(set(x))<2 or len(set(y))<2:raise ValueError('变量为常量，无法计算相关性；请更换温区或变量')
 p=pearsonr(x,y);s=spearmanr(x,y)
 return {'n':len(valid),'excluded':len(rows)-len(valid),'total':len(rows),'pearson':round(float(p.statistic),6),'spearman':round(float(s.statistic),6),'pearson_p':float(p.pvalue),'spearman_p':float(s.pvalue),'points':[{'x':a,'y':b} for a,b in zip(x,y)],'version':ALGORITHM_VERSION,'warning':'相关性不代表因果。线路时长、货种和装卸频次可能同时影响超温与损耗。研究使用创建时样本快照。'}
