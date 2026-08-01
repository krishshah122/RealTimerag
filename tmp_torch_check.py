import traceback
import sys
try:
    import torch
    print('TORCH_OK', getattr(torch, '__file__', None))
    print('ATTRS', [a for a in dir(torch) if a.startswith('amp')][:50])
except Exception:
    traceback.print_exc()
    sys.exit(1)
