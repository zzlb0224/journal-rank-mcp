import csv, os
path = r'D:\1\opencode\journal-rank-mcp\data\中科院分区表及JCR原始数据文件\XR2026-UTF8.csv'
with open(path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    diff = 0
    same = 0
    for r in reader:
        j = r.get('Journal', '').strip()
        km = r.get('刊名', '').strip()
        if j and km:
            if j.lower() == km.lower():
                same += 1
            else:
                diff += 1
                if diff <= 5:
                    print(f'  Journal="{j}" vs 刊名="{km}"')
    print(f'\nsame: {same}, diff: {diff}')
