# modules/inference.py
import numpy as np
import pandas as pd
import streamlit as st
import joblib
from typing import Dict, List, Tuple, Any

from modules.ai_lib import preprocess_data

MODEL_PATH = "models/final_churn_model.pkl"
THRESH_PATH = "models/risk_thresholds.pkl"

@st.cache_resource
def load_artifacts() -> Tuple[Any, Dict, List[str]]:
    """
    Streamlit rerun에도 안정적으로:
      - 모델/threshold 로드 캐시
      - 학습 피처 목록 확보
    """
    model = joblib.load(MODEL_PATH)
    thresholds = joblib.load(THRESH_PATH)

    if hasattr(model, "feature_names_in_"):
        model_features = list(model.feature_names_in_)
    else:
        raise ValueError(
            "모델에 feature_names_in_가 없습니다. "
            "학습 시 사용한 MODEL_FEATURES를 별도 파일로 저장해서 로드하는 방식으로 바꿔야 합니다."
        )

    return model, thresholds, model_features

def _as_prob(model, X: pd.DataFrame) -> np.ndarray:
    if not hasattr(model, "predict_proba"):
        raise ValueError("모델에 predict_proba가 없습니다. 저장 형태를 확인해야 합니다.")

    proba = model.predict_proba(X)
    if len(proba.shape) == 2 and proba.shape[1] >= 2:
        return proba[:, 1]
    return proba.ravel()

def _get_thresholds(thresholds: Any) -> Dict[str, float]:
    """
    thresholds.pkl 형식이 dict든 list든 최소한 티어 기준을 뽑아냄.
    우선순위:
      - dict에 T99/T95/T90 있으면 그대로 사용
      - 아니면 dict values 정렬/ list/tuple 앞 3개를 T90/T95/T99로 가정
    """
    if isinstance(thresholds, dict):
        keys = thresholds.keys()
        if all(k in keys for k in ["T90", "T95", "T99"]):
            return {"T90": float(thresholds["T90"]), "T95": float(thresholds["T95"]), "T99": float(thresholds["T99"])}

        vals = sorted([float(v) for v in thresholds.values()])
        if len(vals) >= 3:
            # 낮은→높은 순으로 들어왔다고 가정: T90 < T95 < T99
            return {"T90": vals[0], "T95": vals[1], "T99": vals[2]}

    if isinstance(thresholds, (list, tuple)) and len(thresholds) >= 3:
        vals = [float(v) for v in thresholds[:3]]
        vals = sorted(vals)
        return {"T90": vals[0], "T95": vals[1], "T99": vals[2]}

    raise ValueError("thresholds.pkl 형태를 해석할 수 없습니다. (dict with T90/T95/T99 권장)")

def assign_risk_tier(p: float, T90: float, T95: float, T99: float) -> str:
    if p >= T99:
        return "Tier 1"  # Extreme Risk
    elif p >= T95:
        return "Tier 2"  # Very High Risk
    elif p >= T90:
        return "Tier 3"  # High Risk
    else:
        return "Tier 4"  # Low Risk

def tier_to_korean_label(tier: str) -> str:
    mapping = {
        "Tier 1": "즉시 이탈 위험",
        "Tier 2": "고위험",
        "Tier 3": "중위험",
        "Tier 4": "안정",
    }
    return mapping.get(tier, tier)

def predict_and_build(df_raw: pd.DataFrame, id_col: str = "customer_id") -> pd.DataFrame:
    """
    업로드 raw df -> 전처리 -> 확률 예측 -> 티어/라벨 생성 -> 결과 df 반환
    """
    if df_raw is None or len(df_raw) == 0:
        raise ValueError("업로드 데이터가 비어 있습니다.")

    if id_col not in df_raw.columns:
        raise ValueError(f"ID 컬럼 '{id_col}'이(가) 업로드 파일에 없습니다. 현재 컬럼 일부: {list(df_raw.columns)[:30]}")

    model, thresholds_obj, model_features = load_artifacts()
    th = _get_thresholds(thresholds_obj)

    # 전처리: object -> numeric / one-hot / 컬럼정렬
    X = preprocess_data(df_raw, model_features=model_features, id_col=id_col)

    # 예측
    p = _as_prob(model, X).astype(float)

    out = pd.DataFrame({
        id_col: df_raw[id_col].astype(str),
        "churn_proba": np.round(p, 6),
    })

    out["risk_tier"] = out["churn_proba"].apply(lambda v: assign_risk_tier(v, th["T90"], th["T95"], th["T99"]))
    out["risk_group"] = out["risk_tier"].apply(tier_to_korean_label)

    return out.sort_values("churn_proba", ascending=False).reset_index(drop=True)
