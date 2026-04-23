# Mission: Create "latent-space-dance-off" - Ollama Benchmarking Application with SVG Generation and AI Judging

## Project Context
See `.opencode/docs/project-design.md` for comprehensive technical design.

## File Manifest
| Action | File Path | Description | Dependencies |
|--------|-----------|-------------|--------------|
| CREATE | pyproject.toml | Project config & dependencies | - |
| CREATE | README.md | Project documentation | - |
| CREATE | .env.example | Environment variables template | - |
| CREATE | main.py | CLI entry point | All modules |
| CREATE | src/__init__.py | Package initialization | - |
| CREATE | src/model_manager.py | Ollama model management | - |
| CREATE | src/svg_generator.py | SVG generation logic | model_manager.py |
| CREATE | src/svg_judge.py | SVG judging logic | - |
| CREATE | src/benchmark.py | Benchmark recording | - |
| CREATE | src/ranking.py | Aggregation & ranking | benchmark.py |
| CREATE | src/config.py | Configuration management | - |
| CREATE | src/utils.py | Utility functions | - |
| CREATE | data/__init__.py | Data package | - |
| CREATE | tests/__init__.py | Test package | - |
| [x] | main.py | CLI working | - |

## Work Assignments

### T1: Project Setup | parallel-group:1 | agent:Worker | status: completed
- [x] S1.1: CREATE `pyproject.toml` | agent:Worker | file:pyproject.toml | size:S
- [x] S1.2: CREATE `README.md` | agent:Worker | file:README.md | size:S
- [x] S1.3: CREATE `.env.example` | agent:Worker | file:.env.example | size:S

### T2: Core Infrastructure | parallel-group:2 | agent:Worker | status: completed
#### T2.1: Configuration System
- [x] S2.1.1: CREATE `src/config.py` | agent:Worker | file:src/config.py | size:M
#### T2.2: Utilities
- [x] S2.2.1: CREATE `src/utils.py` | agent:Worker | file:src/utils.py | size:S
#### T2.3: Package Initialization
- [x] S2.3.1: CREATE `src/__init__.py` | agent:Worker | file:src/__init__.py | size:X
- [x] S2.3.2: CREATE `data/__init__.py` | agent:Worker | file:data/__init__.py | size:X
- [x] S2.3.3: CREATE `tests/__init__.py` | agent:Worker | file:tests/__init__.py | size:X

### T3: Model Management | parallel-group:3 | agent:Worker | status: completed
#### P3.1: Model Manager Core
- [x] S3.1.1: CREATE `src/model_manager.py` | agent:Worker | file:src/model_manager.py | size:M
#### P3.2: SVG Generator
- [x] S3.2.1: CREATE `src/svg_generator.py` | agent:Worker | file:src/svg_generator.py | depends:S3.1.1 | size:M

### T4: Judging & Benchmarking | parallel-group:4 | agent:Worker | status: completed
#### P4.1: SVG Judge System
- [x] S4.1.1: CREATE `src/svg_judge.py` | agent:Worker | file:src/svg_judge.py | size:M
#### P4.2: Benchmark Recorder
- [x] S4.2.1: CREATE `src/benchmark.py` | agent:Worker | file:src/benchmark.py | size:M
#### P4.3: Ranking System
- [x] S4.3.1: CREATE `src/ranking.py` | agent:Worker | file:src/ranking.py | depends:S4.2.1 | size:M

### T5: CLI Application | parallel-group:5 | agent:Worker | status: completed
#### P5.1: Main CLI Entry Point
- [x] S5.1.1: CREATE `main.py` | agent:Worker | file:main.py | depends:S3.1.1,S3.2.1,S4.1.1,S4.2.1,S4.3.1 | size:L

### T6: Tests | parallel-group:6 | agent:Worker | status: in_progress
#### P6.1: Model Manager Tests
- [x] S6.1.1: CREATE `tests/test_model_manager.py` | agent:Worker | file:tests/test_model_manager.py | depends:S3.1.1 | size:M
#### P6.2: SVG Generator Tests
- [x] S6.2.1: CREATE `tests/test_svg_generator.py` | agent:Worker | file:tests/test_svg_generator.py | depends:S3.2.1 | size:S
#### P6.3: SVG Judge Tests
- [x] S6.3.1: CREATE `tests/test_svg_judge.py` | agent:Worker | file:tests/test_svg_judge.py | depends:S4.1.1 | size:M
#### P6.4: Benchmark Tests
- [x] S6.4.1: CREATE `tests/test_benchmark.py` | agent:Worker | file:tests/test_benchmark.py | depends:S4.2.1 | size:S
#### P6.5: Ranking Tests
- [x] S6.5.1: CREATE `tests/test_ranking.py` | agent:Worker | file:tests/test_ranking.py | depends:S4.3.1 | size:M

### T7: Final Quality Pass | parallel-group:7 | agent:Reviewer | depends:ALL
#### P7.1: Build & Test Verification
- [x] S7.1.1: VERIFY CLI works | agent:Reviewer | size:S
- [x] S7.1.2: VERIFY imports work | agent:Reviewer | size:S

### T8: Documentation & Cleanup | parallel-group:8 | agent:Worker | depends:P7
#### P8.1: Final Documentation
- [x] S8.1.1: UPDATE `README.md` with usage examples | agent:Worker | file:README.md | size:S

---

## Success Criteria
1. All tests pass (model_manager, svg_generator, svg_judge, benchmark, ranking)
2. CLI commands work as documented
3. Benchmark runs complete without errors
4. Leaderboard shows correct rankings
5. All SVGs are saved and accessible
6. Code is linted

## Notes
- Ollama needs to be running locally for actual SVG generation
- All imports verified working
- CLI commands functional
