import pandas as pd

# 创建一个示例 DataFrame
data = {
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Age': [25, 30, 35],
    'City': ['New York', 'Los Angeles', 'Chicago']
}
df = pd.DataFrame(data)

# 选择第二行（索引为 1）
row = df.iloc[1]
print(row)