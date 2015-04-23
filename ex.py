def Loop1(n):
    s = 0
    for i in range(1, n + 1):
        for j in range(1, i * i + 1):
            s = s + 1
    return s

def Loop2(n):
    s = 0
    for i in range(1, n + 1):
        for j in range(1, i + 1):
            s = s + 1
    return s

def Loop3(n):
    i = 0
    j = n
    while i <= j:
        i = i + 1
        j = j - 1
    return i

def Loop4a(n):
    i = n
    while i > 0:
        i = (i - 1) / 2

def Loop5(n):
    s = 1
    i = 1
    while i <= n:
        for j in range(1, i + 1):
            s = s + 1
        i = i * 2
    return s

def Loop6(n):
    i = 1
    s = 1
    while i * i <= n:
        i = i + i
        s = s + 1
    return s

def Loop1(n):
    s = 0
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            s = s + 1
    return s

def Loop2(n):
    i = 1
    while i <= n:
        j = i
        while j > 1:
            j = j / 2
        i = i + 1

def nlogn(n):
    for i in range(n):
        j = 1
        while j < n:
            j += j

def logn(n):
    j = 1
    while j < n:
        j += j
