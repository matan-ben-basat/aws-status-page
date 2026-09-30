// NOTE: For SCM polling to trigger builds on push, this file must live at the
// root of the polled repository (the status-page app repo), not just here.
// Copy it there (or configure the Jenkins job's "Pipeline script path") once
// the Jenkins job is created.

pipeline {
    agent any

    triggers {
        // Polling, not a webhook — Jenkins stays closed to inbound internet traffic.
        pollSCM('H/5 * * * *')
    }

    environment {
        // The Terraform/Ansible/Jenkins config repo, checked out once on the Jenkins
        // server (separately from this job, which polls the app repo instead).
        INFRA_DIR     = '/opt/statuspage-infra'
        ANSIBLE_DIR   = '/opt/statuspage-infra/ansible'
        TERRAFORM_DIR = '/opt/statuspage-infra/terraform'
        AWS_REGION    = 'us-east-1'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test / Lint') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet flake8
                    flake8 --select=E9,F63,F7,F82 --exclude=.venv .
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                // Real Django unit tests (manage.py test), not just the syntax
                // gate above. Needs a configuration.py with a live DB/Redis —
                // Jenkins now has Docker (added for the EKS pipeline), so this
                // spins up throwaway Postgres/Redis containers to satisfy that,
                // reusing docker/configuration.py.template from the app repo.
                sh '''
                    docker network create testnet-$BUILD_NUMBER
                    docker run -d --name testpg-$BUILD_NUMBER --network testnet-$BUILD_NUMBER \
                        -e POSTGRES_DB=statuspage -e POSTGRES_USER=statuspage -e POSTGRES_PASSWORD=testpass \
                        postgres:15-alpine
                    docker run -d --name testredis-$BUILD_NUMBER --network testnet-$BUILD_NUMBER redis:7-alpine
                    sleep 5

                    docker build -t statuspage-test:$BUILD_NUMBER .
                    docker run --rm --network testnet-$BUILD_NUMBER \
                        -e DB_NAME=statuspage -e DB_USER=statuspage -e DB_PASSWORD=testpass \
                        -e DB_HOST=testpg-$BUILD_NUMBER -e DB_PORT=5432 \
                        -e REDIS_HOST=testredis-$BUILD_NUMBER -e REDIS_PORT=6379 \
                        -e SECRET_KEY=test-secret-key-for-ci-only-1234567890 \
                        -e SITE_URL=http://localhost \
                        --entrypoint bash statuspage-test:$BUILD_NUMBER \
                        -c "envsubst < statuspage/configuration.py.template > statuspage/configuration.py && python manage.py test components extras incidents maintenances users utilities metrics subscribers queuing"
                        # Only the apps actually in INSTALLED_APPS. Bare
                        # `manage.py test` auto-discovers every tests.py in
                        # the source tree, including disabled optional
                        # plugin apps (sp_external_status_providers,
                        # sp_uptimerobot) that fail to import because
                        # they're not registered — a pre-existing gap in
                        # the vendored code, not something introduced here.
                '''
            }
            post {
                always {
                    sh '''
                        docker rm -f testpg-$BUILD_NUMBER testredis-$BUILD_NUMBER || true
                        docker network rm testnet-$BUILD_NUMBER || true
                        docker rmi statuspage-test:$BUILD_NUMBER || true
                    '''
                }
            }
        }

        stage('Build') {
            steps {
                sh '''
                    git rev-parse --short HEAD > .release_tag
                    echo "Release tag: $(cat .release_tag)"
                '''
            }
        }

        stage('Terraform Init') {
            steps {
                sh '''
                    cd "$TERRAFORM_DIR"
                    terraform init -backend-config=backend.hcl -input=false
                '''
            }
        }

        stage('Deploy') {
            steps {
                // group_vars/all/vault.yml is ansible-vault encrypted; the
                // password file lives only on the Jenkins server's disk
                // (/var/lib/jenkins/.vault_pass, jenkins-owned, mode 600),
                // never in git.
                sh '''
                    cd "$ANSIBLE_DIR"
                    export SSM_BUCKET_NAME=$(terraform -chdir="$TERRAFORM_DIR" output -raw ssm_transfer_bucket)
                    RDS_SECRET_ARN=$(terraform -chdir="$TERRAFORM_DIR" output -raw rds_secret_arn)
                    RDS_ENDPOINT=$(terraform -chdir="$TERRAFORM_DIR" output -raw rds_endpoint)
                    ALB_DNS=$(terraform -chdir="$TERRAFORM_DIR" output -raw alb_dns_name)
                    REDIS_IP=$(terraform -chdir="$TERRAFORM_DIR" output -raw redis_private_ip)

                    ansible-playbook -i inventory/aws_ec2.yml playbooks/site.yml \
                        --limit role_app \
                        --vault-password-file /var/lib/jenkins/.vault_pass \
                        -e "ansible_aws_ssm_bucket_name=${SSM_BUCKET_NAME}" \
                        -e "rds_secret_arn=${RDS_SECRET_ARN}" \
                        -e "rds_endpoint=${RDS_ENDPOINT}" \
                        -e "alb_dns_name=${ALB_DNS}" \
                        -e "redis_private_ip=${REDIS_IP}" \
                        -e "deploy_key_path=/var/lib/jenkins/.ssh/statuspage_deploy" \
                        -e "app_version=$(cat "$WORKSPACE/.release_tag" 2>/dev/null || echo main)"
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    cd "$TERRAFORM_DIR"
                    ALB_DNS=$(terraform output -raw alb_dns_name)
                    bash "$INFRA_DIR/jenkins/scripts/health_check.sh" "$ALB_DNS"
                '''
            }
        }
    }

    post {
        failure {
            echo "Pipeline failed — see stage logs above. (Add email/Slack notification here if desired.)"
        }
    }
}
