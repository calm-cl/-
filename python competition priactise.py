import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    n_str, m_str = line.split()
    m = int(m_str)
    mod = 0
    for c in n_str:
        mod = (mod * 10 + int(c)) % m
    print(mod)

n = input().strip()
sign = 1
if n[0] == '-':
    sign = -1
    n = n[1:]

reversed_str = n[::-1].lstrip('0')
if not reversed_str:
    print(0)
else:
    print(int(reversed_str) * sign)


dp = [0] * 21
dp[2] = 1
dp[3] = 2

for i in range(4, 21):
    dp[i] = (i-1) * (dp[i-1] + dp[i-2])

n = int(input())
print(dp[n])


n = int(input())
binary = bin(n)[2:]
print(f"{n:11d}-->{binary}")


import math
n, m = map(int, input().split())
ans = math.factorial(n) // (math.factorial(m) * math.factorial(n-m))
print(ans)

t = int(input())
h = t // 3600
m = (t % 3600) // 60
s = t % 60
print(f"{h}:{m}:{s}")

n = int(input())

def build(k):
    if k == 1:
        return "A"
    return build(k-1) + chr(ord('A')+k-1) + build(k-1)

print(build(n))


v = int(input())
n = int(input())
a = [int(input()) for _ in range(n)]

dp = [False]*(v+1)
dp[0] = True

for num in a:
    for j in range(v, num-1, -1):
        if dp[j - num]:
            dp[j] = True

max_w = 0
for i in range(v, -1, -1):
    if dp[i]:
        max_w = i
        break

print(v - max_w)

