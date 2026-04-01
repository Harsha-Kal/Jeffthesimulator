import traceback, sys
try:
    import main
except Exception as e:
    with open("crash.txt", "w") as f:
        traceback.print_exc(file=f)
        print("CRASH LOGGED")
