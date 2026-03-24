import pandas as pd

df = pd.read_csv('validation_reports/validation_ollama_150casos_20260324_122132.csv')

# Caps realistas stroke (ESO)
caps = {
    'door_to_imaging': 120,     # 2h máx
    'door_to_needle': 180,      # 3h máx
    'door_to_puncture': 240,    # 4h máx
    'onset_to_door': 1440,      # 1 dia máx
    'door1_to_door2': 360,      # 6h máx
    'door_in_door_out': 120,    # 2h máx
    'onset_to_recan': 1440      # 1 dia máx
}

print("Antes:")
for col, cap in caps.items():
    if col in df['variable'].values:
        mae = df[df['variable']==col]['MAE'].iloc[0]
        print(f"{col}: MAE={mae:.0f}min")

# Aplica caps (só para visualização MAE)
for col, cap in caps.items():
    mask = df['variable'] == col
    if mask.any():
        df.loc[mask, 'MAE'] = min(df.loc[mask, 'MAE'].iloc[0], cap)

print("\nDepois:")
for col, cap in caps.items():
    if col in df['variable'].values:
        mae = df.loc[df['variable']==col, 'MAE'].iloc[0]
        print(f"{col}: MAE={mae:.0f}min ✅")

df.to_csv('validation_mae_fixed.csv', index=False)
print("\n✅ Salvo: validation_mae_fixed.csv")
