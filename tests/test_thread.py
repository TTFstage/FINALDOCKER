import os


def calculate_optimal_threads(multiplier=2, min_threads=4, max_threads=32):
    """
    Calcola il numero ottimale di thread in base ai core CPU disponibili.
    - multiplier: 2 per app bilanciate, 3-4 per app fortemente I/O-bound (molte query/API)
    - min_threads: valore minimo per garantire reattività anche su CPU single-core
    - max_threads: limite di sicurezza per evitare di saturare la memoria
    """
    try_cores = os.cpu_count()
    # Se per qualche motivo os.cpu_count() restituisce None, usiamo 2 come fallback
    cores = try_cores if try_cores is not None else 2
    
    calculated_threads = cores * multiplier
    
    # Applica i limiti minimo e massimo
    optimal_threads = max(min_threads, min(calculated_threads, max_threads))
    
    print(f"[INFO] Core CPU rilevati: {cores}")
    print(f"[INFO] Thread Waitress ottimali: {optimal_threads}")
    
    return optimal_threads

threads_count = calculate_optimal_threads(multiplier=2)