#!/usr/bin/env bash
# Usage: ./deploy.sh <env> <app|all>   e.g. ./deploy.sh staging pmp
set -euo pipefail
ENV=${1:?env required}
APP=${2:-all}
echo "Deploying $APP to $ENV..."
kubectl apply -f infrastructure/kubernetes/namespaces.yaml
case $APP in
  pmp|all) kubectl apply -f infrastructure/kubernetes/pmp/ ;;&
  idp|all) kubectl apply -f infrastructure/kubernetes/idp/ ;;&
  api|all) kubectl apply -f infrastructure/kubernetes/api/ ;;
esac
echo "Done. Watch: kubectl rollout status -n consent-platform deploy/$APP-backend"
