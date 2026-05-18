output "cluster_name" {
  description = "EKS cluster name"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "EKS Kubernetes version"
  value       = aws_eks_cluster.main.version
}

output "s3_bucket_name" {
  description = "S3 bucket for ticket attachments"
  value       = aws_s3_bucket.attachments.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.attachments.arn
}

output "helpdesk_irsa_role_arn" {
  description = "IAM role ARN for IRSA — paste into kubernetes/serviceaccount.yaml"
  value       = aws_iam_role.helpdesk_irsa.arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "update_kubeconfig_command" {
  description = "Run this command to connect kubectl to the cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${aws_eks_cluster.main.name}"
}

output "efs_filesystem_id" {
  description = "EFS filesystem ID — paste into kubernetes/storageclass.yaml"
  value       = aws_efs_file_system.helpdesk.id
}
