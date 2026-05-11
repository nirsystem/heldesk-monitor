# HelpDesk Pro — Enterprise Ticket System

> מערכת כרטיסי תמיכה ארגונית המבוססת על Flask, פרוסה על AWS EKS באמצעות CI/CD מלא.
> המערכת מאפשרת ניהול קריאות תמיכה עם תפקידים, הקצאות, צרופות ב-S3, לוח Kanban, ולוגי ביקורת.

---

## ארכיטקטורה

```
Developer → Git Commit → GitHub → GitHub Actions CI/CD
→ Docker Build → DockerHub → AWS EKS (Kubernetes)
→ Flask App → SQLite (/data/) + AWS S3 (attachments)
                    ↑
              Terraform creates:
              VPC + EKS Cluster + S3 Bucket + IAM Roles
```

---

## תפקידים והרשאות

| תפקיד | הרשאות |
|--------|---------|
| **Admin** | הכל — ניהול משתמשים, כל הכרטיסים, דשבורד, לוגים |
| **Technician** | כרטיסים שהוקצו אליו, עדכון סטטוס, תגובות |
| **User** | פתיחת כרטיסים שלו בלבד, צרופות, תגובות |

---

## דרישות מוקדמות

לפני שמתחילים, יש להתקין את כל הכלים הבאים ולוודא שהם עובדים:

| כלי | גרסה מינימלית | לינק הורדה | פקודת בדיקה |
|-----|---------------|------------|-------------|
| Python | 3.11+ | https://www.python.org/downloads/ | `python --version` |
| Docker Desktop | עדכני | https://www.docker.com/products/docker-desktop/ | `docker --version` |
| Terraform | 1.5+ | https://developer.hashicorp.com/terraform/downloads | `terraform --version` |
| AWS CLI | v2 | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html | `aws --version` |
| kubectl | עדכני | https://kubernetes.io/docs/tasks/tools/ | `kubectl version --client` |
| Git | עדכני | https://git-scm.com/downloads | `git --version` |

בנוסף יש צורך ב:

- **חשבון GitHub** — https://github.com/signup
- **חשבון DockerHub + Access Token** — https://hub.docker.com/signup
- **חשבון AWS** עם הרשאות מנהל

---

## שלב 1 — הכנת חשבון AWS

### 1.1 יצירת IAM User

1. היכנס ל-AWS Console: https://console.aws.amazon.com/iam/
2. לחץ על **Users** בתפריט השמאלי
3. לחץ על **Add users**
4. שם המשתמש: `helpdesk-deployer`
5. בחר **Attach policies directly**
6. חפש והוסף את כל ה-Policies הבאות:

```
AmazonEKSFullAccess
AmazonS3FullAccess
AmazonEC2FullAccess
IAMFullAccess
AmazonVPCFullAccess
```

7. לחץ **Next** → **Create user**

### 1.2 יצירת Access Keys

1. לחץ על שם המשתמש `helpdesk-deployer`
2. עבור לטאב **Security credentials**
3. גלול למטה ולחץ **Create access key**
4. בחר **Command Line Interface (CLI)**
5. לחץ **Next** → **Create access key**
6. **שמור את ה-Access Key ID וה-Secret Access Key** — לא תוכל לראות את ה-Secret שוב

### 1.3 הגדרת AWS CLI

```bash
aws configure
# AWS Access Key ID: [הכנס כאן]
# AWS Secret Access Key: [הכנס כאן]
# Default region name: us-east-1
# Default output format: json
```

### 1.4 בדיקת חיבור

```bash
aws sts get-caller-identity
```

פלט תקין נראה כך:

```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/helpdesk-deployer"
}
```

אם מופיעה שגיאה — בדוק שהכנסת את ה-Keys נכון ב-`aws configure`.

---

## שלב 2 — הכנת DockerHub

### 2.1 יצירת חשבון

אם אין לך חשבון, הירשם ב: https://hub.docker.com/signup

### 2.2 יצירת Access Token

1. היכנס ל-DockerHub
2. לחץ על שם המשתמש שלך (פינה ימנית עליונה) → **Account Settings**
3. בתפריט השמאלי לחץ **Security**
4. לחץ **New Access Token**
5. שם ל-Token: `github-actions`
6. הרשאות: **Read, Write, Delete**
7. לחץ **Generate**
8. **שמור את ה-Token** — לא תוכל לראות אותו שוב

### 2.3 יצירת Repository

1. בדף הראשי של DockerHub לחץ **Create repository**
2. שם ה-Repository: `helpdesk-pro`
3. נראות: **Public**
4. לחץ **Create**

---

## שלב 3 — הכנת GitHub Repository

### 3.1 יצירת Repository ב-GitHub

1. היכנס ל-GitHub
2. לחץ על **+** (פינה ימנית עליונה) → **New repository**
3. שם: `helpdesk-pro`
4. נראות: **Private** (מומלץ) או Public
5. לחץ **Create repository**

### 3.2 שכפול ה-Repository מקומית

```bash
git clone https://github.com/<USERNAME>/helpdesk-pro.git
cd helpdesk-pro
```

החלף `<USERNAME>` בשם המשתמש שלך ב-GitHub.

### 3.3 הוספת GitHub Secrets

כל ה-Secrets מאוחסנים בצורה מוצפנת ב-GitHub ומועברים ל-Actions בזמן ריצה.

**נווט אל:** `Settings → Secrets and variables → Actions → New repository secret`

הוסף את כל ה-Secrets הבאים אחד אחד:

| Secret Name | מה להכניס | איפה מוצאים |
|-------------|-----------|-------------|
| `AWS_ACCESS_KEY_ID` | ה-Access Key ID של ה-IAM User | AWS Console → IAM → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | ה-Secret Access Key | נשמר בעת יצירת ה-Key |
| `AWS_REGION` | `us-east-1` | קבוע |
| `DOCKERHUB_USERNAME` | שם המשתמש שלך ב-DockerHub | DockerHub → Account Settings |
| `DOCKERHUB_TOKEN` | ה-Token שיצרת | DockerHub → Security |
| `S3_BUCKET_NAME` | `helpdesk-attachments-yourname` | תבחר שם ייחודי, תשמור אותו |
| `FLASK_SECRET_KEY` | מחרוזת רנדומלית ארוכה | הרץ: `python -c "import secrets; print(secrets.token_hex(32))"` |

> **חשוב:** שם ה-S3 Bucket חייב להיות ייחודי גלובלית ב-AWS. השתמש בשם שלך כסיומת, למשל `helpdesk-attachments-david2024`.

---

## שלב 4 — בדיקה מקומית עם Docker

לפני שמעלים לענן, חובה לבדוק שהכל עובד על המחשב שלך.

### 4.1 בנה את ה-Docker Image

```bash
docker build -t helpdesk-pro .
```

צפה בפלט — אמור לסיים עם `Successfully built` ו-`Successfully tagged helpdesk-pro:latest`.

### 4.2 הרץ מקומית

```bash
docker run -p 5000:5000 \
  -e FLASK_SECRET_KEY=devsecret123 \
  -e S3_BUCKET_NAME=your-bucket-name \
  -e AWS_REGION=us-east-1 \
  -v $(pwd)/data:/data \
  helpdesk-pro
```

### 4.3 פתח דפדפן

נווט אל: `http://localhost:5000`

### 4.4 רשימת בדיקות מקומיות

לפני שממשיכים לשלב הבא, בצע את כל הבדיקות:

- [ ] דף login עולה
- [ ] כניסה עם `admin` / `Admin@1234` עובדת
- [ ] פתיחת כרטיס חדש עובדת
- [ ] כרטיס מופיע ברשימה
- [ ] עדכון סטטוס עובד
- [ ] Admin Panel נגיש
- [ ] יצירת משתמש חדש עובדת

### 4.5 עצור את ה-Container

```bash
# בטרמינל נפרד
docker ps
docker stop <CONTAINER_ID>
```

---

## שלב 5 — Deploy תשתית עם Terraform

Terraform יצור אוטומטית את כל משאבי ה-AWS: VPC, EKS Cluster, Node Group, S3 Bucket, ו-IAM Roles.

### 5.1 כנס לתיקיית Terraform

```bash
cd terraform
```

### 5.2 אתחול Terraform

```bash
terraform init
```

פלט תקין מסתיים עם: `Terraform has been successfully initialized!`

### 5.3 תכנון — קרא מה הולך להיווצר

```bash
terraform plan \
  -var="s3_bucket_name=helpdesk-attachments-yourname"
```

קרא את הפלט בעיון — אמור להציג יצירה של כ-20-30 משאבים. אם מופיעות שגיאות — פתור אותן לפני ה-apply.

### 5.4 יצירת התשתית ב-AWS

```bash
terraform apply \
  -var="s3_bucket_name=helpdesk-attachments-yourname"
```

כאשר מוצג `Do you want to perform these actions?` — הקלד `yes` ולחץ Enter.

> **שים לב:** התהליך לוקח **12-18 דקות**. ה-EKS Cluster הוא המשאב הכבד ביותר. אל תבטל את הפקודה.

### 5.5 שמור את ה-Outputs

בסיום ה-apply, Terraform יציג outputs. שמור אותם:

```bash
terraform output
```

תראה ערכים כמו:
- `cluster_name` — שם ה-EKS Cluster
- `s3_bucket_name` — שם ה-Bucket
- `cluster_endpoint` — כתובת ה-API Server

### 5.6 בדיקות ב-AWS Console אחרי Apply

היכנס ל-AWS Console ובדוק:

- [ ] VPC נוצר עם 4 subnets (ב-VPC Console)
- [ ] EKS Cluster בסטטוס **Active** (ב-EKS Console)
- [ ] Node Group עם 3 nodes (ב-EKS → Cluster → Compute)
- [ ] S3 Bucket קיים (ב-S3 Console)
- [ ] IAM Roles נוצרו (ב-IAM → Roles, חפש "helpdesk")

---

## שלב 6 — התחברות ל-Kubernetes

### 6.1 עדכן את ה-kubeconfig

```bash
aws eks update-kubeconfig \
  --region us-east-1 \
  --name helpdesk-pro-cluster
```

פלט תקין: `Updated context arn:aws:eks:us-east-1:...:cluster/helpdesk-pro-cluster in /home/user/.kube/config`

### 6.2 בדוק שמחובר

```bash
kubectl get nodes
```

אמור לראות 3 nodes בסטטוס **Ready**:

```
NAME                           STATUS   ROLES    AGE   VERSION
ip-10-0-1-100.ec2.internal    Ready    <none>   5m    v1.28.x
ip-10-0-2-101.ec2.internal    Ready    <none>   5m    v1.28.x
ip-10-0-3-102.ec2.internal    Ready    <none>   5m    v1.28.x
```

### 6.3 צפה בפרטים

```bash
kubectl get nodes -o wide
```

> **אם ה-nodes לא Ready:** המתן 3 דקות נוספות ונסה שוב. EKS לפעמים לוקח זמן להשלים את רישום ה-nodes. אם אחרי 10 דקות הם עדיין NotReady, עבור לסעיף Troubleshooting.

---

## שלב 7 — הגדרת Kubernetes Secrets

### 7.1 צור Namespace

```bash
kubectl create namespace helpdesk
```

### 7.2 צור Secrets

```bash
kubectl create secret generic helpdesk-secret \
  --from-literal=FLASK_SECRET_KEY=your-long-random-secret-here \
  -n helpdesk
```

החלף `your-long-random-secret-here` בערך ה-FLASK_SECRET_KEY שיצרת קודם.

### 7.3 בדוק שה-Secret נוצר

```bash
kubectl get secrets -n helpdesk
```

פלט תקין:

```
NAME               TYPE     DATA   AGE
helpdesk-secret   Opaque   1      10s
```

### 7.4 עדכן ConfigMap

פתח את הקובץ `kubernetes/configmap.yaml` ועדכן את שם ה-S3 Bucket לשם האמיתי שלך לפני שממשיכים ל-Deploy.

---

## שלב 8 — Deploy ידני ראשון ל-Kubernetes

### 8.1 החל את כל ה-Manifests

```bash
kubectl apply -f kubernetes/
```

פלט תקין:

```
configmap/helpdesk-config created
deployment.apps/helpdesk-app created
service/helpdesk-service created
ingress.networking.k8s.io/helpdesk-ingress created
serviceaccount/helpdesk-sa created
```

### 8.2 בדוק שה-Pods עולים

```bash
kubectl get pods -n helpdesk
```

> **המתן כ-2 דקות** להורדת ה-image ולהפעלה. ה-STATUS יעבור מ-`ContainerCreating` ל-`Running`.

```
NAME                            READY   STATUS    RESTARTS   AGE
helpdesk-app-7d4f9c8b6-abc12   2/2     Running   0          2m
helpdesk-app-7d4f9c8b6-def34   2/2     Running   0          2m
```

### 8.3 עקוב אחרי ה-Logs

```bash
kubectl logs -f deployment/helpdesk-app -n helpdesk
```

צפה ב-logs בזמן אמת. אמור לראות:

```
 * Running on http://0.0.0.0:5000
 * Debug mode: off
```

לחץ `Ctrl+C` לעצירת עקיבת ה-logs.

### 8.4 בדוק Services

```bash
kubectl get svc -n helpdesk
```

### 8.5 בדוק Ingress

```bash
kubectl get ingress -n helpdesk
```

שים לב לעמודה **ADDRESS** — זו הכתובת שדרכה תיגש לאפליקציה. יתכן שתדרוש כ-2-3 דקות להופיע.

---

## שלב 9 — בדיקת CI/CD

### 9.1 הפעל את ה-Pipeline

```bash
echo "# pipeline test" >> README.md
git add .
git commit -m "test: trigger cicd pipeline"
git push
```

### 9.2 עקוב אחרי ה-Pipeline ב-GitHub

1. פתח את ה-Repository ב-GitHub
2. לחץ על הטאב **Actions**
3. לחץ על ה-Workflow שרץ כעת
4. לחץ על שם ה-Job לפתיחת הלוג המלא
5. עקוב אחרי כל שלב

### 9.3 צ'קליסט Pipeline

בדוק שכל השלבים הבאים עברו בירוק:

- [ ] Checkout code
- [ ] Setup Python
- [ ] Install dependencies
- [ ] Smoke test passed
- [ ] Docker build success
- [ ] Docker push to DockerHub
- [ ] AWS credentials configured
- [ ] kubectl connected to EKS
- [ ] kubectl apply success
- [ ] Rollout status: success

### 9.4 בדוק Pods חדשים אחרי ה-Pipeline

```bash
kubectl get pods -n helpdesk
```

תראה pods חדשים עם AGE קצר — Kubernetes מחליף את ה-pods הישנים בגרסה החדשה בצורה רציפה (Rolling Update).

---

## כניסה ראשונה לאפליקציה

### מציאת ה-URL

```bash
kubectl get ingress -n helpdesk
```

העתק את הכתובת מעמודה **ADDRESS**.

**URL:** `http://<EXTERNAL-IP מ-kubectl get ingress>`

### פרטי כניסה ראשוניים

| שדה | ערך |
|-----|-----|
| שם משתמש | `admin` |
| סיסמה | `Admin@1234` |

> **אבטחה:** שנה את סיסמת ה-admin מיד לאחר הכניסה הראשונה.

---

## תרחיש הדגמה מלא לפרזנטציה

בצע את השלבים הבאים לפי הסדר כדי להדגים את כל יכולות המערכת:

1. **כנס כ-admin** — השתמש בפרטים שלעיל
2. **צור משתמש חדש** — שם: `david`, תפקיד: **Technician**
3. **צור משתמש נוסף** — שם: `yossi`, תפקיד: **User**
4. **התנתק** והתחבר כ-`yossi`
5. **פתח כרטיס חדש:**
   - כותרת: `המחשב שלי לא נדלק`
   - עדיפות: **High**
   - קטגוריה: **Hardware**
6. **צרף צילום מסך** לכרטיס
7. **התנתק** והתחבר כ-`admin`
8. **ראה את הכרטיס** ב-Admin Panel
9. **הקצה את הכרטיס** ל-`david`
10. **התנתק** והתחבר כ-`david`
11. **עדכן סטטוס** ל-**In Progress**
12. **הוסף תגובה:** `בודק את הבעיה`
13. **עדכן סטטוס** ל-**Resolved**
14. **הראה את ה-Kanban Board** המעודכן
15. **הראה את ה-Audit Logs** ב-Admin Panel

---

## פקודות שימושיות לניהול שוטף

### צפייה בסטטוס

```bash
# ראה את כל ה-Pods
kubectl get pods -n helpdesk

# ראה Pods + מידע מורחב (node, IP)
kubectl get pods -n helpdesk -o wide

# ראה את כל המשאבים ב-Namespace
kubectl get all -n helpdesk
```

### Logs ו-Debugging

```bash
# לוגים של ה-Deployment
kubectl logs -f deployment/helpdesk-app -n helpdesk

# לוגים של Pod ספציפי
kubectl logs <pod-name> -n helpdesk

# לוגים עם 100 שורות אחרונות
kubectl logs --tail=100 <pod-name> -n helpdesk

# ראה events (לדיבוג בעיות)
kubectl get events -n helpdesk --sort-by='.lastTimestamp'

# תיאור מפורט של Pod (לדיבוג CrashLoop וכו')
kubectl describe pod <pod-name> -n helpdesk
```

### כניסה ל-Pod

```bash
kubectl exec -it <pod-name> -n helpdesk -- /bin/bash
```

### פעולות על Deployment

```bash
# עדכן image ידנית
kubectl set image deployment/helpdesk-app \
  helpdesk=<DOCKERHUB_USERNAME>/helpdesk-pro:latest \
  -n helpdesk

# הפעל מחדש את כל ה-Pods (Rolling Restart)
kubectl rollout restart deployment/helpdesk-app -n helpdesk

# בדוק סטטוס Rollout
kubectl rollout status deployment/helpdesk-app -n helpdesk

# Scale up ל-3 replicas
kubectl scale deployment helpdesk-app --replicas=3 -n helpdesk

# Scale down ל-1 replica
kubectl scale deployment helpdesk-app --replicas=1 -n helpdesk
```

### ניקוי (בסוף הקורס בלבד)

```bash
# מחק את כל המשאבים ב-Namespace
kubectl delete namespace helpdesk

# הרס את כל התשתית ב-AWS
cd terraform && terraform destroy \
  -var="s3_bucket_name=helpdesk-attachments-yourname"
# כתוב: yes
# ⏳ מחכים 10-15 דקות
```

> **אזהרה:** `terraform destroy` ימחק את כל התשתית כולל ה-EKS Cluster, ה-VPC, וה-S3 Bucket. בצע רק בסיום הקורס.

---

## Troubleshooting — בעיות נפוצות ופתרונות

| בעיה | סיבה | פתרון |
|------|------|--------|
| **EKS nodes בסטטוס NotReady** | Node IAM Role חסר Policies | בדוק ב-`iam.tf` שה-Node Role מכיל: `AmazonEKSWorkerNodePolicy` + `AmazonEKS_CNI_Policy` + `AmazonEC2ContainerRegistryReadOnly` |
| **`kubectl`: connection refused** | kubeconfig לא מעודכן | הרץ שוב: `aws eks update-kubeconfig --region us-east-1 --name helpdesk-pro-cluster` |
| **S3 AccessDenied בעת העלאת צרופה** | IRSA לא מוגדר | בדוק annotation על Service Account ב-`deployment.yaml`: `eks.amazonaws.com/role-arn` |
| **DockerHub push failed** | Token פג תוקף | צור Token חדש ב-DockerHub → Security → עדכן את `DOCKERHUB_TOKEN` ב-GitHub Secrets |
| **GitHub Actions נכשל ב-smoke test** | נתיב import שגוי | בדוק את ה-`PYTHONPATH` ואת `sys.path` בפקודת הבדיקה ב-workflow |
| **Pod בסטטוס CrashLoopBackOff** | שגיאה בהפעלת האפליקציה | הרץ: `kubectl logs <pod-name> -n helpdesk` וקרא את שגיאת ה-Python |
| **Pod בסטטוס ImagePullBackOff** | שם image שגוי או Repo פרטי | בדוק `DOCKERHUB_USERNAME` ב-GitHub Secrets ואת שם ה-image ב-`deployment.yaml` |
| **LoadBalancer תקוע ב-Pending** | AWS Load Balancer Controller לא מותקן | הרץ: `helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system` |
| **Terraform apply נכשל על EKS** | הרשאות IAM לא מספיקות | הוסף `EKSFullAccess` + `EC2FullAccess` + `IAMFullAccess` ל-IAM User |
| **SQLite: permission denied** | `/data` לא writable | בדוק שה-`emptyDir` volume מוגדר נכון ב-`deployment.yaml` ושנתיב ה-mount הוא `/data` |
| **כל ה-Pods מראים 0/2 Ready** | readinessProbe נכשל | הרץ: `kubectl describe pod <pod-name> -n helpdesk` וחפש את `Readiness probe failed` |
| **Pipeline ירוק אבל אפליקציה ישנה** | Rollout לא הושלם | הרץ: `kubectl rollout restart deployment/helpdesk-app -n helpdesk` |
| **`aws configure` לא שומר** | Profile שגוי | הרץ: `aws configure --profile default` ובדוק את `~/.aws/credentials` |
| **Terraform: S3 Bucket already exists** | שם Bucket לא ייחודי | שנה את שם ה-Bucket ל-`helpdesk-attachments-<שמך>-<מספר>` |

---

## מבנה הפרויקט

```
helpdesk-pro/
├── app/                    # קוד Flask
│   ├── __init__.py
│   ├── models.py           # מודלי SQLite
│   ├── routes/             # נתיבי API
│   └── templates/          # HTML templates
├── kubernetes/             # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   └── serviceaccount.yaml
├── terraform/              # תשתית AWS
│   ├── main.tf
│   ├── eks.tf
│   ├── vpc.tf
│   ├── s3.tf
│   ├── iam.tf
│   └── variables.tf
├── .github/
│   └── workflows/
│       └── cicd.yml        # GitHub Actions Pipeline
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## סיכום ה-Pipeline

```
git push
    ↓
GitHub Actions מתעורר
    ↓
התקנת Python + dependencies
    ↓
Smoke test (בדיקת imports)
    ↓
docker build -t image:tag .
    ↓
docker push → DockerHub
    ↓
aws eks update-kubeconfig
    ↓
kubectl apply -f kubernetes/
    ↓
kubectl rollout status (בדיקת הצלחה)
    ↓
האפליקציה החדשה חיה ב-EKS
```

---

*פרויקט גמר — קורס DevSecOps | HelpDesk Pro Enterprise Ticket System*
