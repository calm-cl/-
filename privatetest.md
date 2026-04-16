# ==============================
# 智能学院Python大赛 10题全能版
# 本地可直接运行看结果
# ==============================

# 1. A+B 问题
def problem1():
    a, b = map(int, input().split())
    print(a + b)

# 2. 绝对值与平方
def problem2():
    x = float(input())
    print(abs(x))
    print(x ** 2)

# 3. 字符串反转
def problem3():
    s = input().strip()
    print(s[::-1])

# 4. 判断奇偶数
def problem4():
    n = int(input())
    print("Even" if n % 2 == 0 else "Odd")

# 5. 1~N累加和
def problem5():
    n = int(input())
    print(n * (n + 1) // 2)

# 6. 三个数最大值
def problem6():
    a, b, c = map(int, input().split())
    print(max(a, b, c))

# 7. 统计0出现次数
def problem7():
    nums = list(map(int, input().split()))
    print(nums.count(0))

# 8. 斐波那契第N项
def problem8():
    n = int(input())
    if n <= 2:
        print(1)
    else:
        a, b = 1, 1
        for _ in range(3, n+1):
            a, b = b, a+b
        print(b)

# 9. 数字排序输出
def problem9():
    nums = list(map(int, input().split()))
    nums.sort()
    print(' '.join(map(str, nums)))

# 10. 判断质数
def problem10():
    n = int(input())
    if n < 2:
        print("No")
    else:
        flag = True
        for i in range(2, int(n**0.5)+1):
            if n % i == 0:
                flag = False
                break
        print("Yes" if flag else "No")

# ==============================
# 测试入口：想测第几题就改数字
# ==============================
if __name__ == "__main__":
    # 示例：测第1题就写 problem1()
    problem1()
