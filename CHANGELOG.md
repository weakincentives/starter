# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Renamed `MainLoop` to `AgentLoop` throughout the codebase for better alignment with mainstream agent terminology. This pairs well with `EvalLoop` naming convention.
  - `MainLoop` → `AgentLoop`
  - `MainLoopConfig` → `AgentLoopConfig`
  - `MainLoopRequest` → `AgentLoopRequest`
  - `MainLoopResult` → `AgentLoopResult`
