import taichi as ti


ti.init(arch=ti.gpu, default_fp=ti.f64)


# ── Taichi kernels ────────────────────────────────────────────────────────

@ti.kernel
def _dot(a: ti.template(), b: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * b[i]
    return result

@ti.kernel
def _norm(a: ti.template()) -> ti.f64:
    result = 0.0
    for i in a:
        result += a[i] * a[i]
    return ti.sqrt(result)

@ti.kernel
def _matvec(A: ti.template(), x: ti.template(), out: ti.template()):
    for i in out:
        s = 0.0
        for j in range(x.shape[0]):
            s += A[i, j] * x[j]
        out[i] = s

@ti.kernel
def _vec_add(alpha: ti.f64, x: ti.template(), beta: ti.f64,
             y: ti.template(), out: ti.template()):
    """out[i] = alpha*x[i] + beta*y[i]"""
    for i in out:
        out[i] = alpha * x[i] + beta * y[i]

@ti.kernel
def _copy(src: ti.template(), dst: ti.template()):
    for i in dst:
        dst[i] = src[i]



# ── Solver driver ─────────────────────────────────────────────────────────

def pcg(A, b, x, M_inv, tol, maxiter):
    """
    Auto-generated from LaTeX algorithmic environment.
    Backend: Taichi (GPU)
    """
    n = b.shape[0]
    
    # Allocate working vectors
    p = ti.field(ti.f64, shape=n)
    q = ti.field(ti.f64, shape=n)
    r = ti.field(ti.f64, shape=n)
    z = ti.field(ti.f64, shape=n)
    _tmp0 = ti.field(ti.f64, shape=n)
    
    _matvec(A, x, _tmp0)
    _vec_add(1.0, b, -1.0, _tmp0, r)
    M_inv(r, z)
    _copy(z, p)
    rho = _dot(r, z)
    for k in range(0, maxiter):
        _matvec(A, p, q)
        alpha = (rho / _dot(p, q))
        _vec_add(1.0, x, alpha, p, x)
        _vec_add(1.0, r, -alpha, q, r)
        if (_norm(r) < tol):
            return x, k
        M_inv(r, z)
        rho_new = _dot(r, z)
        beta = (rho_new / rho)
        _vec_add(1.0, z, beta, p, p)
        rho = rho_new
    return x, maxiter
