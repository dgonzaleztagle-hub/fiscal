import { NextRequest,NextResponse } from "next/server";
import {demoMutationResponse} from "@/lib/demo-route";
import {fiscalEngineCredentials} from "@/lib/fiscal-runtime";
export async function POST(request:NextRequest){
 const engine=fiscalEngineCredentials();
 if(!engine)return demoMutationResponse(request,"commercial");
 const {baseUrl:base,token}=engine;
 const response=await fetch(new URL("/v1/commercial-documents",base),{method:"POST",headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json","Idempotency-Key":request.headers.get("Idempotency-Key")??crypto.randomUUID()},body:await request.text(),cache:"no-store"});
 return new NextResponse(await response.text(),{status:response.status,headers:{"Content-Type":"application/json"}});
}
