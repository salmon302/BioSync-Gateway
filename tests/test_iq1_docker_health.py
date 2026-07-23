# SPDX-License-Identifier: MIT
"""
IQ-1: Docker Health Check Test
Implements SRS IQ-1 - Verify Docker HEALTHCHECK configuration and /health endpoint

This test validates:
1. The Dockerfile contains a valid HEALTHCHECK instruction
2. The /health endpoint responds correctly with status 200
3. The health check response includes required fields (database, middleware, pulseEngine)
"""

import os
import pytest
import json


class TestIQ1DockerHealthCheck:
    """Test suite for IQ-1 - Docker Health Check"""

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile should contain a HEALTHCHECK instruction"""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "middleware", "Dockerfile"
        )
        
        assert os.path.exists(dockerfile_path), f"Dockerfile not found at {dockerfile_path}"
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        
        assert 'HEALTHCHECK' in content, "Dockerfile must contain HEALTHCHECK instruction"
        assert '/health' in content, "HEALTHCHECK should target /health endpoint"

    def test_healthcheck_config_parameters(self):
        """HEALTHCHECK should have reasonable interval and timeout parameters"""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "middleware", "Dockerfile"
        )
        
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        
        # Verify key HEALTHCHECK parameters exist
        assert '--interval=' in content, "HEALTHCHECK should specify --interval"
        assert '--timeout=' in content, "HEALTHCHECK should specify --timeout"
        assert '--retries=' in content, "HEALTHCHECK should specify --retries"

    def test_health_endpoint_response_structure(self):
        """Health endpoint should return required fields"""
        try:
            from fastapi.testclient import TestClient
            from middleware.api.main import app
            
            client = TestClient(app)
            response = client.get("/api/health")
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            
            data = response.json()
            required_fields = ['database', 'middleware', 'pulseEngine']
            
            for field in required_fields:
                assert field in data, f"Response missing required field: {field}"
            
            # Verify database status is present (may be healthy or unhealthy depending on DB connection)
            assert 'database' in data
            
        except ImportError:
            pytest.skip("FastAPI test dependencies not available")

    def test_health_endpoint_json_content_type(self):
        """Health endpoint should return JSON content type"""
        try:
            from fastapi.testclient import TestClient
            from middleware.api.main import app
            
            client = TestClient(app)
            response = client.get("/api/health")
            
            assert 'application/json' in response.headers.get('content-type', ''), \
                "Response should have JSON content type"
            
        except ImportError:
            pytest.skip("FastAPI test dependencies not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
