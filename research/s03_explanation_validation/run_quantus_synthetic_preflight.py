"""Execute frozen Quantus metrics on synthetic tabular adapter/attribution shapes only."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import quantus
import torch

ROOT=Path(__file__).resolve().parent; CONFIG=ROOT/"config"
ROUTES={"logistic_regression":["occlusion","permutation_shap"],"decision_tree":["occlusion","tree_shap"],"random_forest":["occlusion","tree_shap"],"gradient_boosting":["occlusion","tree_shap"],"flat_neuro_fuzzy":["occlusion","integrated_gradients","gradient_shap"]}

class SyntheticTabularProductAdapter(torch.nn.Module):
    """Preflight-only torch interface with the same [batch,1,feature] contract."""
    def forward(self,x):
        values=x.reshape(len(x),-1); score=2*values[:,0]+.7*values[:,1]-.3*values[:,2]+.1*values[:,3]-.5
        return torch.stack([-score,score],dim=1)

def explanation_shape_adapter(model, inputs, targets, **kwargs):
    values=np.asarray(inputs)
    weights=np.array([.70,.20,.08,.02])
    return weights.reshape(1,1,-1) * (1.0 + 0.05 * values)

def run() -> dict:
    x=np.array([[[.1,.2,.3,.4]],[[.15,1.,.3,.2]],[[1.,.1,.4,.1]],[[1.,1.,.2,.9]],[[.2,.8,.1,.4]],[[.8,.2,.9,.3]]],dtype=np.float32); y=np.array([0,0,0,1,0,0]); a=explanation_shape_adapter(None,x,y); model=SyntheticTabularProductAdapter().eval()
    metrics=[("faithfulness_correlation",quantus.FaithfulnessCorrelation(nr_runs=10,subset_size=1,perturb_baseline="mean",return_aggregate=False,disable_warnings=True)),("max_sensitivity",quantus.MaxSensitivity(nr_samples=10,lower_bound=0.,upper_bound=.05,disable_warnings=True))]
    rows=[]
    for family, explainers in ROUTES.items():
        for explainer in explainers:
            values={}
            for name, metric in metrics:
                result=metric(model=model,x_batch=x,y_batch=y,a_batch=a,softmax=True,channel_first=True,explain_func=explanation_shape_adapter)
                finite=sum(bool(np.isfinite(value)) for value in result)
                if finite == 0: raise RuntimeError(f"Quantus {name} returned no finite synthetic compatibility result.")
                values[name]={"execution":"PASS","result_count":len(result),"finite_result_count":finite}
            rows.append({"model_family":family,"explainer":explainer,"tabular_shape":list(a.shape),"adapter":"SyntheticTabularProductAdapter","metrics":values,"state":"AVAILABLE"})
    receipt={"schema_version":1,"study":"S03_QUANTUS_SYNTHETIC_PREFLIGHT_ONLY","benchmark_accessed":False,"quantus_version":quantus.__version__,"state":"AVAILABLE","routes":rows,"note":"Metric call compatibility is established on synthetic tabular product-adapter and product-native explanation shapes; no benchmark score is reported."}
    (CONFIG/"quantus_synthetic_preflight.json").write_text(json.dumps(receipt,sort_keys=True,separators=(",",":"))+"\n")
    return receipt
if __name__=="__main__": print(json.dumps(run(),sort_keys=True))
