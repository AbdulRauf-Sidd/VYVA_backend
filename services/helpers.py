import random
import string

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Example usage:
random_string = generate_random_string()
print(random_string)