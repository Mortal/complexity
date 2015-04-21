def Loop1(n):
    s = 0
    for i in range(1, n + 1):
        for j in range(1, i * i + 1):
            s = s + 1

def Loop2(n):
    s = 0
    for i in range(n + 1):
        for j in range(n + 1):
            s = s + 1

def Loop3(n):
    i = 0
    j = n
    while i <= j:
        i = i + 1
        j = j - 1

def Loop4(n):
    i = n
    while i > 0:
        if i % 2 == 1:
            i = i - 1
        else:
            i = i / 2

def Loop5(n):
    s = 1
    i = 1
    while i <= n:
        for j in range(1, i + 1):
            s = s + 1
        i = i * 2

def Loop6(n):
    i = 1
    while i * i <= n:
        i = i + i
