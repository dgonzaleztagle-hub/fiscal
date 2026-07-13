from dataclasses import dataclass
@dataclass(frozen=True)
class UsageDecision:
 allowed:bool;classification:str;reason:str
class FairUsePolicy:
 """Guardas antiabuso; no son cupos comerciales visibles."""
 LIMITS={"commercial_document":100_000,"inventory_movement":1_000_000,"public_proof":10_000}
 def decide(self,*,operation:str,monthly_count:int)->UsageDecision:
  limit=self.LIMITS.get(operation)
  if limit is None:return UsageDecision(True,"normal","Operación sin umbral industrial")
  if monthly_count<limit:return UsageDecision(True,"normal","Uso pyme normal")
  return UsageDecision(False,"enterprise_review","Volumen industrial: requiere revisión de capacidad y plan empresarial")
