resource "aws_security_group" "efs" {
  name        = "${var.cluster_name}-efs-sg"
  description = "Allow NFS from VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-efs-sg"
  }
}

resource "aws_efs_file_system" "helpdesk" {
  encrypted = true

  tags = {
    Name = "${var.cluster_name}-efs"
  }
}

resource "aws_efs_mount_target" "helpdesk" {
  count           = 2
  file_system_id  = aws_efs_file_system.helpdesk.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# ── IRSA — EFS CSI Driver ─────────────────────────────────────────────────────
resource "aws_iam_role" "efs_csi_irsa" {
  name = "${var.cluster_name}-efs-csi-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:efs-csi-controller-sa"
          "${replace(aws_iam_openid_connect_provider.eks.url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "efs_csi_irsa" {
  role       = aws_iam_role.efs_csi_irsa.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy"
}

resource "aws_eks_addon" "efs_csi" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "aws-efs-csi-driver"
  service_account_role_arn = aws_iam_role.efs_csi_irsa.arn

  depends_on = [aws_eks_node_group.main]
}
