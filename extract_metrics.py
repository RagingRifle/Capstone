import sqlite3, json
import pandas as pd

conn = sqlite3.connect('results/simulation.db')
df = pd.read_sql_query('SELECT * FROM run_results ORDER BY recorded_at DESC', conn)
df['sc_short'] = df['scenario'].apply(lambda x: '_'.join(x.split('_')[:-1]) if '_' in x else x)
df_latest = df.drop_duplicates(subset=['sc_short','strategy'], keep='first')

cols = ['sc_short','strategy','tasks_completed','avg_latency_ms','p95_latency_ms',
        'sla_violation_rate','throughput_per_s','total_energy_j','task_completion_rate']
print(df_latest[cols].to_string(index=False))
print()
for _, row in df_latest.iterrows():
    try:
        dist = json.loads(row['node_distribution']) if row['node_distribution'] else {}
    except Exception:
        dist = {}
    key = str(row['sc_short']) + '_' + str(row['strategy'])
    print(key + ': ' + str(dist))
conn.close()
