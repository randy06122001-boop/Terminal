from fastapi import FastAPI
import sys
import os
import pkg_resources

app = FastAPI()

@app.get("/api/health")
def health_check():
    """
    Diagnostic endpoint to see exactly what's inside the Vercel environment.
    """
    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    return {
        "status": "online",
        "python_version": sys.version,
        "environment": "Vercel/Lambda" if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else "Local",
        "package_count": len(installed_packages),
        "packages": installed_packages,
        "path": sys.path
    }
