# ai_lib.py
import pandas as pd
import numpy as np
from typing import List, Optional

# 범주형 변수 (One-Hot Encoding 대상)
CORE_CATEGORICAL_FEATURES = ["gender", "region", "income_band", "card_grade"]

# 모델에 넣을 핵심 수치형/행동 변수 (프로젝트 정의)
HIGH_IMPORTANCE_FEATURES = [
    "marketing_open_rate_6m", "tenure_months", "complaints_6m", "age",
    "spent_change_ratio",
    "login_m1", "login_m2", "login_m3",
    "spent_m1", "spent_m2", "spent_m3",
    "txn_m1", "txn_m2", "txn_m3",
]

# 파생변수 계산에 필요한 원본 컬럼
_SPENT_M1_M6 = [f"spent_m{i}" for i in range(1, 7)]

def _ensure_columns(
    df: pd.DataFrame,
    numeric_cols: List[str],
    categorical_cols: List[str],
    id_col: str = "customer_id",
    fill_numeric: float = 0.0,
    fill_category: str = "UNKNOWN",
) -> pd.DataFrame:
    """
    누락 컬럼이 있어도 추론이 깨지지 않도록 기본값으로 보정.
    (데모/운영 안정성 목적)
    """
    out = df.copy()

    if id_col not in out.columns:
        raise ValueError(f"ID 컬럼 '{id_col}'이(가) 업로드 파일에 없습니다. 현재 컬럼 일부: {list(out.columns)[:30]}")

    for c in numeric_cols:
        if c not in out.columns:
            out[c] = fill_numeric

    for c in categorical_cols:
        if c not in out.columns:
            out[c] = fill_category

    return out

def preprocess_data(
    df_input: pd.DataFrame,
    model_features: List[str],
    id_col: str = "customer_id",
) -> pd.DataFrame:
    """
    raw 입력(df_input)을 모델 입력 형태로 변환:
      - 파생변수 생성
      - 범주형 One-Hot
      - 학습 피처(model_features)와 컬럼/순서 완전 일치(reindex)
      - ID 컬럼 제거
    """
    if df_input is None or len(df_input) == 0:
        raise ValueError("입력 데이터가 비어 있습니다.")

    df_temp = df_input.copy()

    # 0) 누락 컬럼 보정 (파생변수 계산 + 핵심피처 + 범주형 + ID)
    needed_numeric_for_ratio = _SPENT_M1_M6 + [
        "marketing_open_rate_6m", "tenure_months", "complaints_6m", "age",
        "login_m1", "login_m2", "login_m3",
        "spent_m1", "spent_m2", "spent_m3",
        "txn_m1", "txn_m2", "txn_m3",
    ]
    df_temp = _ensure_columns(
        df_temp,
        numeric_cols=needed_numeric_for_ratio,
        categorical_cols=CORE_CATEGORICAL_FEATURES,
        id_col=id_col,
    )

    # 1) 타입 정리(숫자형 강제 변환)
    for c in needed_numeric_for_ratio:
        df_temp[c] = pd.to_numeric(df_temp[c], errors="coerce").fillna(0.0)

    for c in CORE_CATEGORICAL_FEATURES:
        df_temp[c] = df_temp[c].astype(str).fillna("UNKNOWN")

    # 2) 파생변수 생성
    df_temp["recent_3m_spent"] = df_temp["spent_m1"] + df_temp["spent_m2"] + df_temp["spent_m3"]
    df_temp["past_3m_spent"] = df_temp["spent_m4"] + df_temp["spent_m5"] + df_temp["spent_m6"]
    df_temp["spent_change_ratio"] = df_temp["recent_3m_spent"] / (df_temp["past_3m_spent"] + 1.0)

    # 3) 필요한 컬럼만 선택 (ID + 핵심 수치 + 범주형)
    features_to_use = [id_col] + HIGH_IMPORTANCE_FEATURES + CORE_CATEGORICAL_FEATURES
    # 존재하는 컬럼만 선택(안전)
    df_filtered = df_temp[[c for c in features_to_use if c in df_temp.columns]].copy()

    # 4) One-Hot Encoding
    df_encoded = pd.get_dummies(df_filtered, columns=CORE_CATEGORICAL_FEATURES, dtype=int)

    # 5) 학습 피처와 완전 일치
    df_processed = df_encoded.reindex(columns=model_features, fill_value=0)

    # 6) ID는 모델 입력에서 제거(혹시 포함되어 있으면 제거)
    if id_col in df_processed.columns:
        df_processed = df_processed.drop(columns=[id_col])

    # 최종 dtype 보장
    for col in df_processed.columns:
        if df_processed[col].dtype == "object":
            df_processed[col] = pd.to_numeric(df_processed[col], errors="coerce").fillna(0.0)

    return df_processed
