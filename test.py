import time

last_error = None 
error = 1 
while True:
    try:
        if last_error != error:
            last_error = error
            print(error)
            print(last_error)
            

    finally:
        time.sleep(5)